import os

os.environ['SECRET_KEY'] = 'dev-secret-key'
os.environ.pop('DATABASE_URL', None)

import letterbox.settings as s

print('SECRET_KEY_SET=' + str(bool(s.SECRET_KEY)))
print('DATABASE_CONFIGURED=' + str(bool(s.DATABASE_URL)))
print('HAS_SQLITE=' + str(s.DATABASE_URL.startswith('sqlite:///')))
print('IMPORT_OK=1')
