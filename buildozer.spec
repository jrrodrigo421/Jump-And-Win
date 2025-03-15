[app]
title = JumpAndWin
package.name = jumpandwin
package.domain = com.yourcompany
source.dir = .
source.include_exts = py,png,jpg,wav,ttf,otf
requirements = python3, pygame-ce, psycopg2, python-dotenv

# Versão do app
version = 1.0

# Android permissions
android.permissions = INTERNET

# Orientação e ícones
orientation = portrait
icon.filename = %(source.dir)s/assets/icon.png

# SDK configurações
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk = 33
