from django.db import migrations


class Migration(migrations.Migration):
    """One agent prompt instead of assignments: rename the per-user template
    field and drop the Assignment docs (activity rows that referenced them
    keep their entity_type/label; there was no FK)."""

    dependencies = [
        ('agents', '0002_mcpsession'),
        ('activity', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='agentconfig',
            old_name='assignment_template',
            new_name='prompt_template',
        ),
        migrations.DeleteModel(name='Assignment'),
    ]
