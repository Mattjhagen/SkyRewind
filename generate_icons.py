#!/usr/bin/env python3
"""
Generate PNG icons from favicon.svg for PWA/Apple support.

Usage: python3 generate_icons.py

Generates:
- frontend/icons/icon-192.png (192x192, any purpose)
- frontend/icons/icon-512.png (512x512, maskable - mark in central 80% safe area)
- frontend/icons/apple-touch-icon.png (180x180, Apple home screen)
"""

from PIL import Image, ImageDraw

def create_icon(size, output_path, is_maskable=False):
    """Create a gold rounded-square icon with white play triangle."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # For maskable icons, keep design in central 80% (40% radius from center)
    if is_maskable:
        margin = int(size * 0.1)  # 10% margin on each side
    else:
        margin = int(size * 0.1)

    # Gold rounded rectangle background
    corner_radius = int((size - 2 * margin) * 0.2)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=corner_radius,
        fill='#FBBF24'
    )

    # White play triangle (centered)
    triangle_margin = int(size * 0.35)
    triangle_coords = [
        (triangle_margin, triangle_margin),
        (triangle_margin, size - triangle_margin),
        (size - triangle_margin, size // 2)
    ]
    draw.polygon(triangle_coords, fill='white')

    img.save(output_path, 'PNG')
    print(f'Generated {output_path} ({size}x{size})')

if __name__ == '__main__':
    import os
    os.makedirs('frontend/icons', exist_ok=True)

    create_icon(192, 'frontend/icons/icon-192.png')
    create_icon(512, 'frontend/icons/icon-512.png', is_maskable=True)
    create_icon(180, 'frontend/icons/apple-touch-icon.png')

    print('\nIcons generated successfully!')
    print('To regenerate: python3 generate_icons.py')
