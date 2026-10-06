"""Recording helpers + the serializer mixin that makes logging automatic.

Changes are expressed with the serializer's own representation (names for
FKs, strings for decimals/dates), so a row reads like the UI does:
  {"amount": {"from": "150.00", "to": "160.00"},
   "account": {"from": null, "to": "Joint current"}}
"""
from .context import resolve_actor_and_source
from .models import ActivityLog


def record_activity(action, entity_type, entity_id, entity_label='', changes=None):
    actor, source, token, session = resolve_actor_and_source()
    return ActivityLog.objects.create(
        actor=actor, source=source, token=token, session=session,
        action=action, entity_type=entity_type, entity_id=entity_id,
        entity_label=(entity_label or '')[:255], changes=changes or {},
    )


def diff(before, after):
    return {key: {'from': before.get(key), 'to': after.get(key)}
            for key in after if before.get(key) != after.get(key)}


def _is_blank(value):
    return value in (None, '', [], {})


class ActivityLoggedSerializerMixin:
    """Mixin for ModelSerializers on logged entities. Subclasses set:

    activity_entity  — entity_type string
    activity_fields  — {display_name: representation_key} to track
    activity_label() — optional; defaults to the instance's name
    """
    activity_entity = None
    activity_fields = {}

    def activity_label(self, instance):
        return getattr(instance, 'name', None) or str(instance)

    def activity_snapshot(self, instance):
        data = self.to_representation(instance)
        return {name: data.get(key) for name, key in self.activity_fields.items()}

    def create(self, validated_data):
        instance = super().create(validated_data)
        after = self.activity_snapshot(instance)
        record_activity(
            'create', self.activity_entity, instance.pk, self.activity_label(instance),
            {k: {'from': None, 'to': v} for k, v in after.items() if not _is_blank(v)},
        )
        return instance

    def update(self, instance, validated_data):
        before = self.activity_snapshot(instance)
        instance = super().update(instance, validated_data)
        changes = diff(before, self.activity_snapshot(instance))
        if changes:
            record_activity('update', self.activity_entity, instance.pk,
                            self.activity_label(instance), changes)
        return instance

    def record_delete(self, instance):
        """Call BEFORE deleting, so the snapshot still resolves relations."""
        before = self.activity_snapshot(instance)
        return record_activity(
            'delete', self.activity_entity, instance.pk, self.activity_label(instance),
            {k: {'from': v, 'to': None} for k, v in before.items() if not _is_blank(v)},
        )


def delete_logged(serializer_cls, instance):
    """Log then delete, for the viewsets and MCP tools."""
    serializer_cls().record_delete(instance)
    instance.delete()
