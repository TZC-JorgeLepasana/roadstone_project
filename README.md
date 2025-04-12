<<<<<<< HEAD
# Roadstone Project\n\nDjango project for data processing
=======
# roadstone_project
>>>>>>> 799af194a34072ccb4e7060ed6d2e67c6df98bbc


CELERY WORKER COMMAND FOR DEVELOPMENT

TERMINAL 1 : py manage.py runserver
TERMINAL 2 : celery -A roadstone_project worker --loglevel=info --pool=solo
TERMINAL 3 : celery -A roadstone_project beat --loglevel=info
