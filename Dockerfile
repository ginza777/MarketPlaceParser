# Rasmiy Python 3.11 versiyasidan foydalanamiz
FROM python:3.11-slim

# Atrof-muhit o'zgaruvchilari
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Ishchi papka yaratamiz
WORKDIR /app

# 1-QADAM: Kerakli tizim paketlari, Chromium va uning drayverini o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium brauzeri va unga mos drayver
    chromium \
    chromium-driver \
    # Selenium ishlashi uchun virtual ekran va uning bog'liqligi
    xvfb \
    xauth \
    # PostgreSQL bilan ishlash uchun
    build-essential \
    libpq-dev \
    # Boshqa kerakli kutubxonalar
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2-QADAM: Python kutubxonalarini o'rnatish
COPY ./requirements /app/requirements
RUN pip install --no-cache-dir -r requirements/production.txt


# 3-QADAM: Loyiha kodini va skriptlarni nusxalash
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

COPY . /app/

# Kirish nuqtasini belgilaymiz
ENTRYPOINT ["/app/entrypoint.sh"]