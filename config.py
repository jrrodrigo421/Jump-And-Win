import platform
import pygame

SYSTEM = platform.system()
# Verifica se o evento de toque existe (Pygame-CE oferece FINGERDOWN)
IS_MOBILE = hasattr(pygame, 'FINGERDOWN')

if IS_MOBILE:
    BUTTON_SCALE = 1.5  # Botões maiores para telas touch
    FONT_SIZE = 32
    SMALL_FONT_SIZE = 24
else:
    BUTTON_SCALE = 1.0
    FONT_SIZE = 24
    SMALL_FONT_SIZE = 18
