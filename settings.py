import dj_database_url


SECRET_KEY = 'django-migration-docs'
# Install the tests as an app so that we can make test models
INSTALLED_APPS = ['migration_docs', 'migration_docs.tests']
# Database url comes from the DATABASE_URL env var
DATABASES = {'default': dj_database_url.config()}
