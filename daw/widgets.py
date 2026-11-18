"""Small reusable UI helpers."""

import pygame

from .theme import *

BTN_DISABLED = (38, 38, 42)
BTN_DISABLED_TEXT = (90, 90, 95)


class Button:
    def __init__(self, rect, label, dropdown=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.dropdown = dropdown
        self.pressed_until = 0
        # A disabled button is greyed out and ignores clicks.
        self.disabled = False

    def contains(self, pos):
        return not self.disabled and self.rect.collidepoint(pos)

    def flash(self, duration=65):
        self.pressed_until = pygame.time.get_ticks() + duration

    def draw(self, screen, font, active=False, active_color=BTN_ACTIVE):
        now = pygame.time.get_ticks()
        color = active_color if active else BTN_COLOR
        if now < self.pressed_until:
            color = FLASH_COLOR
        if self.disabled:
            color = BTN_DISABLED

        pygame.draw.rect(screen, color, self.rect, border_radius=4)
        pygame.draw.rect(screen, (10, 10, 10), self.rect, 1, border_radius=4)

        if self.dropdown:
            section_w = 18
            section = pygame.Rect(self.rect.right - section_w, self.rect.y + 1, section_w - 1, self.rect.height - 2)
            pygame.draw.rect(screen, DROPDOWN_ARROW_BG, section)
            pygame.draw.line(screen, (10, 10, 10), (section.left, section.top), (section.left, section.bottom))
            points = [(section.centerx - 3, section.centery - 2), (section.centerx + 3, section.centery - 2), (section.centerx, section.centery + 3)]
            pygame.draw.polygon(screen, BTN_DISABLED_TEXT if self.disabled else MUTED_TEXT, points)
            text_area_right = section.left - 3
        else:
            text_area_right = self.rect.right

        if self.disabled:
            text_color = BTN_DISABLED_TEXT
        elif now < self.pressed_until:
            text_color = (20, 20, 20)
        else:
            text_color = TEXT_COLOR

        text = font.render(self.label, True, text_color)
        tx = self.rect.x + (text_area_right - self.rect.x - text.get_width()) // 2
        ty = self.rect.y + (self.rect.height - text.get_height()) // 2
        screen.blit(text, (tx, ty))


def draw_arrow(screen, font, x, y, direction="right"):
    """Draw a small text arrow; this is deliberately subtle."""
    symbol = ">" if direction == "right" else "v"
    screen.blit(font.render(symbol, True, MUTED_TEXT), (x, y))
