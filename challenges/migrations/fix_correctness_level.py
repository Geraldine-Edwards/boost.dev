from django.db import migrations, connection, models

def set_default_correctness_level(apps, schema_editor):
    ChallengeSolution = apps.get_model('challenges', 'ChallengeSolution')
    for solution in ChallengeSolution.objects.all():
        if solution.is_correct and (not hasattr(solution, 'correctness_level') or not solution.correctness_level):
            solution.correctness_level = 'correct'
        elif not hasattr(solution, 'correctness_level') or not solution.correctness_level:
            solution.correctness_level = 'incorrect'
        solution.save()

def add_correctness_level_column(apps, schema_editor):
    # Check if the column exists
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(challenges_challengesolution);")
        columns = [row[1] for row in cursor.fetchall()]
        if 'correctness_level' not in columns:
            # Add the column if it doesn't exist
            cursor.execute(
                "ALTER TABLE challenges_challengesolution "
                "ADD COLUMN correctness_level TEXT DEFAULT 'correct';"
            )

class Migration(migrations.Migration):

    dependencies = [
        ('challenges', '0001_initial'),  # Adjust this to the latest migration number
    ]

    operations = [
        migrations.RunPython(add_correctness_level_column),
        migrations.RunPython(set_default_correctness_level),
    ]