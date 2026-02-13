import cv2
import numpy as np

class VisionProcessor:
    @staticmethod
    def detect_violin_body(image_path: str, view_type='front'):
        """
        Detects the bounding box of the violin body.
        Uses a robust vertical width-profile analysis to find the 'bulge' of the body
        and ignore the 'stick' of the neck.
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            # Preprocessing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Thresholding
            # Standard Otsu on inverted image (assuming light background)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Cleanup
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Vertical Width Profile (how many foreground pixels in each row)
            width_profile = np.sum(thresh > 0, axis=1)
            
            # Smooth the profile
            window = max(11, int(len(width_profile) / 30))
            if window % 2 == 0: window += 1
            smooth_profile = np.convolve(width_profile, np.ones(window)/window, mode='same')
            
            # Find the "Body" region
            # The body is a large contiguous region where width is significantly higher than the neck.
            # Usually neck/scroll is < 30% of max body width.
            max_w = np.max(smooth_profile)
            if max_w == 0: return None
            
            # We look for the largest contiguous block where width > 40% of max width
            threshold = 0.40 * max_w
            is_body = smooth_profile > threshold
            
            # Find contiguous regions
            from scipy.ndimage import label
            labels, num_features = label(is_body)
            
            if num_features == 0: return None
            
            # Find the region with the most area (integral of width)
            best_region = -1
            max_integral = 0
            for i in range(1, num_features + 1):
                integral = np.sum(smooth_profile[labels == i])
                if integral > max_integral:
                    max_integral = integral
                    best_region = i
            
            y_indices = np.where(labels == best_region)[0]
            y_start, y_end = y_indices[0], y_indices[-1]
            
            # Crop height slightly to avoid picking up the very top of the neck if threshold was loose
            # Usually the body is a bit more compact.
            h_detected = y_end - y_start
            
            # Horizontal Bounds in that region
            body_mask = thresh[y_start:y_end, :]
            x_sum = np.sum(body_mask, axis=0)
            x_indices = np.where(x_sum > 0)[0]
            
            if len(x_indices) == 0:
                return (0, y_start, img.shape[1], h_detected)
            
            x_start, x_end = x_indices[0], x_indices[-1]
            
            return (int(x_start), int(y_start), int(x_end - x_start), int(y_end - y_start))
            
        except Exception as e:
            print(f"VisionProcessor Error: {e}")
            return None
