"""
Natal Chart Visualization Tool - Cosmic Transit Map Style
Generates circular natal charts with nebula-inspired colors and metro map clarity.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for MCP
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from matplotlib.patches import Wedge, Circle
from pathlib import Path
from typing import Dict, Any, Optional, List

# Zodiac sign data (0° Aries = 0°, going counterclockwise)
SIGNS = [
    ('Aries', '♈', 0, 'Fire'),
    ('Taurus', '♉', 30, 'Earth'),
    ('Gemini', '♊', 60, 'Air'),
    ('Cancer', '♋', 90, 'Water'),
    ('Leo', '♌', 120, 'Fire'),
    ('Virgo', '♍', 150, 'Earth'),
    ('Libra', '♎', 180, 'Air'),
    ('Scorpio', '♏', 210, 'Water'),
    ('Sagittarius', '♐', 240, 'Fire'),
    ('Capricorn', '♑', 270, 'Earth'),
    ('Aquarius', '♒', 300, 'Air'),
    ('Pisces', '♓', 330, 'Water'),
]

# Element colors - Nebula inspired
ELEMENT_COLORS = {
    'Fire': '#FF6B35',      # Bright coral-orange
    'Earth': '#52B788',     # Rich teal-green
    'Air': '#FFD23F',       # Warm yellow
    'Water': '#4895EF',     # Bright blue
}

# Background and structural colors
BACKGROUND = '#0A1128'      # Deep space navy
LINES = '#E8E8E8'           # Soft white for degree marks
HOUSE_LINES = '#6C757D'     # Muted gray
ACCENT_GOLD = '#FFB703'     # Gold for ASC/MC

# Planet symbols
PLANET_SYMBOLS = {
    'Sun': '☉',
    'Moon': '☽',
    'Mercury': '☿',
    'Venus': '♀',
    'Mars': '♂',
    'Jupiter': '♃',
    'Saturn': '♄',
    'Uranus': '♅',
    'Neptune': '♆',
    'Pluto': '♇',
}

# Planet colors - Nebula inspired
PLANET_COLORS = {
    'Sun': '#FFD60A',       # Bright yellow-gold
    'Moon': '#CAF0F8',      # Pale blue-white
    'Mercury': '#FF9E00',   # Orange
    'Venus': '#90E0EF',     # Aqua-cyan
    'Mars': '#FF006E',      # Hot pink-red
    'Jupiter': '#8338EC',   # Royal purple
    'Saturn': '#FB5607',    # Burnt orange
    'Uranus': '#00B4D8',    # Electric cyan
    'Neptune': '#7209B7',   # Deep purple
    'Pluto': '#D62828',     # Deep red
}


def sign_to_absolute_degree(sign_name: str, degree_in_sign: float) -> float:
    """Convert sign + degree to absolute 0-360 degree."""
    sign_starts = {name: start for name, symbol, start, element in SIGNS}
    return sign_starts[sign_name] + degree_in_sign


def absolute_to_chart_angle(absolute_degree: float, ascendant_degree: float) -> float:
    """
    Convert absolute zodiac degree to chart angle.
    Chart has Ascendant at 9 o'clock (180° in matplotlib coords).
    Zodiac runs counterclockwise.
    """
    offset = 180 - ascendant_degree
    angle = (absolute_degree + offset) % 360
    return angle


def draw_star_field(ax, num_stars=150):
    """Draw a subtle star field in the background."""
    np.random.seed(42)  # Reproducible star positions
    
    # Generate random positions
    angles = np.random.uniform(0, 2*np.pi, num_stars)
    radii = np.random.uniform(0.3, 1.15, num_stars)
    sizes = np.random.uniform(0.5, 3, num_stars)
    
    # Convert to cartesian
    x = radii * np.cos(angles)
    y = radii * np.sin(angles)
    
    # Draw stars with varying opacity
    for i in range(num_stars):
        alpha = np.random.uniform(0.3, 0.9)
        ax.plot(x[i], y[i], 'o', color='white', markersize=sizes[i], 
               alpha=alpha, zorder=0)


def draw_zodiac_wheel(ax, ascendant_degree: float):
    """Draw the outer zodiac wheel with element colors."""
    radius_outer = 1.0
    radius_inner = 0.85
    
    for i, (name, symbol, start_deg, element) in enumerate(SIGNS):
        # Get element color
        color = ELEMENT_COLORS[element]
        
        # Convert to chart angles
        start_angle = absolute_to_chart_angle(start_deg, ascendant_degree)
        end_angle = absolute_to_chart_angle((start_deg + 30) % 360, ascendant_degree)
        
        # Handle wrapping around 360°
        if end_angle < start_angle:
            wedge1 = Wedge((0, 0), radius_outer, start_angle, 360, 
                          width=radius_outer-radius_inner, 
                          facecolor=color, edgecolor=LINES, linewidth=1, alpha=0.8)
            wedge2 = Wedge((0, 0), radius_outer, 0, end_angle, 
                          width=radius_outer-radius_inner, 
                          facecolor=color, edgecolor=LINES, linewidth=1, alpha=0.8)
            ax.add_patch(wedge1)
            ax.add_patch(wedge2)
        else:
            wedge = Wedge((0, 0), radius_outer, start_angle, end_angle, 
                         width=radius_outer-radius_inner, 
                         facecolor=color, edgecolor=LINES, linewidth=1, alpha=0.8)
            ax.add_patch(wedge)
        
        # Place sign symbol (white for contrast)
        mid_angle = absolute_to_chart_angle(start_deg + 15, ascendant_degree)
        mid_rad = np.radians(mid_angle)
        label_radius = (radius_outer + radius_inner) / 2
        x = label_radius * np.cos(mid_rad)
        y = label_radius * np.sin(mid_rad)
        ax.text(x, y, symbol, fontsize=18, ha='center', va='center', 
               weight='bold', color='white', zorder=3)


def draw_degree_markers(ax, ascendant_degree: float):
    """Draw degree markers around the outer edge."""
    radius = 1.02
    
    # Draw markers every 5 degrees
    for degree in range(0, 360, 5):
        angle = absolute_to_chart_angle(degree, ascendant_degree)
        rad = np.radians(angle)
        
        # Longer tick every 10 degrees
        if degree % 10 == 0:
            inner_r = 0.98
            linewidth = 1.5
        else:
            inner_r = 0.99
            linewidth = 0.8
        
        x_outer = radius * np.cos(rad)
        y_outer = radius * np.sin(rad)
        x_inner = inner_r * np.cos(rad)
        y_inner = inner_r * np.sin(rad)
        
        ax.plot([x_inner, x_outer], [y_inner, y_outer], 
               color=LINES, linewidth=linewidth, alpha=0.6, zorder=2)


def draw_houses(ax, houses: Dict[str, Dict], ascendant_degree: float):
    """Draw house divisions."""
    radius = 0.85
    
    for house_num in range(1, 13):
        house_key = str(house_num)
        if house_key in houses:
            cusp_absolute = sign_to_absolute_degree(
                houses[house_key]['sign'],
                houses[house_key]['degree']
            )
            
            cusp_angle = absolute_to_chart_angle(cusp_absolute, ascendant_degree)
            cusp_rad = np.radians(cusp_angle)
            
            x_inner = 0.3 * np.cos(cusp_rad)
            y_inner = 0.3 * np.sin(cusp_rad)
            x_outer = radius * np.cos(cusp_rad)
            y_outer = radius * np.sin(cusp_rad)
            
            ax.plot([x_inner, x_outer], [y_inner, y_outer], 
                   color=HOUSE_LINES, linewidth=1.5, alpha=0.7, zorder=2)
            
            # Label house number with subtle background
            label_radius = 0.72
            x_label = label_radius * np.cos(cusp_rad)
            y_label = label_radius * np.sin(cusp_rad)
            ax.text(x_label, y_label, str(house_num), 
                   fontsize=11, ha='center', va='center',
                   color=LINES, weight='bold',
                   bbox=dict(boxstyle='circle,pad=0.3', 
                           facecolor=BACKGROUND, 
                           edgecolor=HOUSE_LINES, 
                           linewidth=1, alpha=0.9), zorder=4)


def draw_planets(ax, planets: Dict[str, Dict], ascendant_degree: float):
    """Draw planets with glowing effect."""
    planet_radius = 0.6
    
    for planet_name, data in planets.items():
        if planet_name not in PLANET_SYMBOLS:
            continue
            
        absolute_deg = sign_to_absolute_degree(data['sign'], data['degree'])
        chart_angle = absolute_to_chart_angle(absolute_deg, ascendant_degree)
        chart_rad = np.radians(chart_angle)
        
        x = planet_radius * np.cos(chart_rad)
        y = planet_radius * np.sin(chart_rad)
        
        color = PLANET_COLORS.get(planet_name, LINES)
        
        # Draw glow effect (larger circle behind)
        glow = Circle((x, y), 0.04, color=color, alpha=0.3, zorder=5)
        ax.add_patch(glow)
        
        # Draw planet symbol
        ax.text(x, y, PLANET_SYMBOLS[planet_name], 
               fontsize=16, ha='center', va='center',
               color=color, weight='bold',
               bbox=dict(boxstyle='circle,pad=0.35', 
                       facecolor=BACKGROUND, 
                       edgecolor=color, 
                       linewidth=2, alpha=0.95), zorder=6)


def create_natal_chart(planets: Dict[str, Dict], 
                       houses: Dict[str, Dict], 
                       points: Dict[str, Dict],
                       chart_title: str = "Natal Chart",
                       output_path: Optional[str] = None) -> str:
    """
    Create a natal chart visualization and save to file.
    
    Args:
        planets: Dict of planet positions {name: {sign: str, degree: float}}
        houses: Dict of house cusps {house_num: {sign: str, degree: float}}
        points: Dict with Ascendant and MC
        chart_title: Title for the chart
        output_path: Where to save the chart (default: natal_chart.png)
    
    Returns:
        Path to the saved chart image
    """
    if output_path is None:
        output_path = "natal_chart.png"
    
    # Create figure with dark background
    fig, ax = plt.subplots(1, 1, figsize=(14, 14), facecolor=BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    ax.set_aspect('equal')
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.axis('off')
    
    ascendant_absolute = sign_to_absolute_degree(
        points['Ascendant']['sign'],
        points['Ascendant']['degree']
    )
    
    # Draw layers from back to front
    draw_star_field(ax, num_stars=150)
    draw_zodiac_wheel(ax, ascendant_absolute)
    draw_degree_markers(ax, ascendant_absolute)
    draw_houses(ax, houses, ascendant_absolute)
    draw_planets(ax, planets, ascendant_absolute)
    
    # Mark Ascendant with gold line
    asc_angle = 180  # Ascendant at 9 o'clock
    asc_rad = np.radians(asc_angle)
    ax.plot([0, 1.0 * np.cos(asc_rad)], [0, 1.0 * np.sin(asc_rad)],
           color=ACCENT_GOLD, linewidth=3.5, alpha=0.9, 
           label='Ascendant', zorder=7)
    
    # Mark MC (if available in points, otherwise use House 10)
    if 'MC' in points:
        mc_absolute = sign_to_absolute_degree(points['MC']['sign'], 
                                             points['MC']['degree'])
    elif '10' in houses:
        # MC is the same as House 10 cusp
        mc_absolute = sign_to_absolute_degree(houses['10']['sign'],
                                             houses['10']['degree'])
    else:
        mc_absolute = None
    
    if mc_absolute is not None:
        mc_angle = absolute_to_chart_angle(mc_absolute, ascendant_absolute)
        mc_rad = np.radians(mc_angle)
        ax.plot([0, 0.85 * np.cos(mc_rad)], [0, 0.85 * np.sin(mc_rad)],
               color=ACCENT_GOLD, linewidth=3.5, alpha=0.7, 
               label='MC', linestyle='--', zorder=7)
    
    # Center point
    ax.plot(0, 0, 'o', color=ACCENT_GOLD, markersize=10, zorder=8)
    
    # Title with cosmic styling
    plt.title(chart_title, fontsize=20, weight='bold', 
             color=LINES, pad=30, family='sans-serif')
    
    # Legend with custom styling
    legend = ax.legend(loc='upper right', fontsize=11, 
                      frameon=True, fancybox=True)
    legend.get_frame().set_facecolor(BACKGROUND)
    legend.get_frame().set_edgecolor(ACCENT_GOLD)
    legend.get_frame().set_alpha(0.9)
    for text in legend.get_texts():
        text.set_color(LINES)
    
    plt.tight_layout()
    
    # Save
    output_path = Path(output_path).expanduser().resolve()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', 
               facecolor=BACKGROUND, edgecolor='none')
    plt.close(fig)
    
    return str(output_path)
