import math

class Viewport:
    """
    Separa lógica de zoom/pan do render - FIX do bug base_scale recalculado todo frame
    """
    def __init__(self, w0, h0, view_w, view_h, right_w):
        left_w = view_w - right_w
        w0 = max(1, int(w0)); h0 = max(1, int(h0))
        self.w0 = w0
        self.h0 = h0
        # FIX: imagem 78% da largura, não 62%
        self.base_scale = min((view_h-160)/h0, max(1, left_w)/w0)
        self.base_scale = max(0.05, self.base_scale)
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.view_w = view_w
        self.view_h = view_h
        self.left_w = left_w
        self.right_w = right_w

    def orig_to_disp(self, ox, oy):
        return int(ox*self.base_scale*self.zoom+self.pan_x), int(oy*self.base_scale*self.zoom+self.pan_y)

    def disp_to_orig(self, dx, dy, oy_off=0):
        bs = self.base_scale*self.zoom or 0.15
        return int((dx-self.pan_x)/bs), int((dy-oy_off-self.pan_y)/bs)

    def zoom_at(self, mx, my, factor, oy_off=0):
        """Zoom centrado no mouse - melhora fluidez"""
        new_z = max(0.1, min(20.0, self.zoom*factor))
        f = new_z/self.zoom if self.zoom!=0 else 1.0
        vx = mx-self.pan_x
        vy = (my-oy_off)-self.pan_y
        self.pan_x = mx-vx*f
        self.pan_y = (my-oy_off)-vy*f
        self.zoom = new_z

    def reset_fit(self):
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0

    def clamp_pan(self, view_h, oy_off):
        img_w = self.w0*self.base_scale*self.zoom
        img_h = self.h0*self.base_scale*self.zoom
        min_px = min(0, self.left_w-img_w)
        max_px = max(0, self.left_w-img_w)
        min_py = min(0, (view_h-40)-img_h)
        max_py = max(0, (view_h-40)-img_h)
        self.pan_x = max(min_px, min(max_px, self.pan_x))
        self.pan_y = max(min_py, min(max_py, self.pan_y))
