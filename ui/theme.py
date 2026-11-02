THEME = {
    'bg': (243,244,246),
    'panel_toolbar': (255,255,255),
    'panel_tab': (250,250,251),
    'panel_inspector': (250,250,251),
    'panel_status': (255,255,255),
    'text_main': (40,44,52),
    'text_dim': (118,124,134),
    'border': (223,226,231),
    'accent': (235,99,37),
    'accent_hover': (250,150,90),
    'success': (74,163,22),
    'danger': (38,38,220),
    'card': (255,255,255),
    'card_alt': (246,247,249),
    'field': (243,244,246),
    'shadow': (226,228,233),
    'accent_soft': (252,238,229),
}

def gerar_cor_familia_infinita(familia_id):
    """Gera cor distinta via golden ratio HSV - suporta infinitas famílias"""
    import colorsys
    h = (familia_id * 0.618033988749895) % 1.0
    s = 0.7 + (familia_id % 3)*0.1
    v = 0.85
    r,g,b = colorsys.hsv_to_rgb(h,s,v)
    return (int(b*255), int(g*255), int(r*255))  # BGR
