from django.db import migrations


def promote_first_user(apps, schema_editor):
    """Registration is now invite-only and admins manage members, so an
    existing deployment needs an admin: the earliest account, if none is
    staff yet."""
    User = apps.get_model('accounts', 'User')
    if User.objects.filter(is_staff=True).exists():
        return
    first = User.objects.order_by('date_joined').first()
    if first is not None:
        first.is_staff = True
        first.save(update_fields=['is_staff'])


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_invite')]
    operations = [migrations.RunPython(promote_first_user, migrations.RunPython.noop)]
