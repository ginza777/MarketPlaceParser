#!/bin/sh

# Migratsiyalarni amalga oshirish
echo "Applying database migrations..."
python manage.py migrate --noinput

# Asosiy buyruqni ishga tushirish (docker-compose.yml'dagi command)
exec "$@"