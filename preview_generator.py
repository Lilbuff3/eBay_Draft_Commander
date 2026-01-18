"""
Listing Preview Generator for eBay Draft Commander Pro
Generate HTML preview of how listing will appear on eBay
"""
from pathlib import Path
from typing import Dict, List, Optional
import base64
import html


class PreviewGenerator:
    """Generate eBay-style listing previews"""
    
    def __init__(self):
        """Initialize preview generator"""
        self.template = self._get_template()
    
    def _get_template(self) -> str:
        """Get HTML template for preview"""
        return '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Listing Preview</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .preview-banner {
            background: #3665f3;
            color: white;
            padding: 10px 20px;
            text-align: center;
            font-size: 14px;
        }
        
        .listing {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .listing-header {
            display: flex;
            gap: 30px;
            padding: 20px;
        }
        
        .images-section {
            flex: 0 0 400px;
        }
        
        .main-image {
            width: 100%;
            height: 400px;
            object-fit: contain;
            background: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
        .thumbnails {
            display: flex;
            gap: 8px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        
        .thumbnail {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border: 2px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .thumbnail.active {
            border-color: #3665f3;
        }
        
        .details-section {
            flex: 1;
        }
        
        .title {
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #191919;
        }
        
        .price {
            font-size: 28px;
            font-weight: 700;
            color: #191919;
            margin-bottom: 20px;
        }
        
        .condition {
            display: inline-block;
            background: #f0f0f0;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 14px;
            margin-bottom: 15px;
        }
        
        .buy-button {
            display: block;
            width: 100%;
            background: #3665f3;
            color: white;
            border: none;
            padding: 15px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 24px;
            cursor: pointer;
            margin-bottom: 10px;
        }
        
        .cart-button {
            display: block;
            width: 100%;
            background: white;
            color: #3665f3;
            border: 2px solid #3665f3;
            padding: 13px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 24px;
            cursor: pointer;
        }
        
        .shipping-info {
            margin-top: 20px;
            padding: 15px;
            background: #f8f8f8;
            border-radius: 8px;
        }
        
        .shipping-info h4 {
            font-size: 14px;
            margin-bottom: 8px;
        }
        
        .shipping-info p {
            font-size: 13px;
            color: #555;
        }
        
        .description-section {
            padding: 20px;
            border-top: 1px solid #eee;
        }
        
        .description-section h3 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #191919;
        }
        
        .description-content {
            font-size: 14px;
            line-height: 1.7;
        }
        
        .description-content h2 {
            font-size: 16px;
            margin: 15px 0 10px;
        }
        
        .description-content ul {
            margin-left: 20px;
            margin-bottom: 15px;
        }
        
        .specifics-section {
            padding: 20px;
            border-top: 1px solid #eee;
        }
        
        .specifics-section h3 {
            font-size: 18px;
            margin-bottom: 15px;
        }
        
        .specifics-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .specific-item {
            display: flex;
            font-size: 14px;
        }
        
        .specific-label {
            flex: 0 0 150px;
            color: #767676;
        }
        
        .specific-value {
            flex: 1;
            font-weight: 500;
        }
        
        @media (max-width: 768px) {
            .listing-header {
                flex-direction: column;
            }
            .images-section {
                flex: none;
            }
            .specifics-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="preview-banner">
        ⚠️ PREVIEW - This is how your listing will appear on eBay
    </div>
    
    <div class="container">
        <div class="listing">
            <div class="listing-header">
                <div class="images-section">
                    {{MAIN_IMAGE}}
                    <div class="thumbnails">
                        {{THUMBNAILS}}
                    </div>
                </div>
                
                <div class="details-section">
                    <h1 class="title">{{TITLE}}</h1>
                    <div class="condition">{{CONDITION}}</div>
                    <div class="price">${{PRICE}}</div>
                    
                    <button class="buy-button">Buy It Now</button>
                    <button class="cart-button">Add to cart</button>
                    
                    <div class="shipping-info">
                        <h4>📦 Shipping</h4>
                        <p>{{SHIPPING_INFO}}</p>
                    </div>
                </div>
            </div>
            
            <div class="specifics-section">
                <h3>Item specifics</h3>
                <div class="specifics-grid">
                    {{SPECIFICS}}
                </div>
            </div>
            
            <div class="description-section">
                <h3>Item description</h3>
                <div class="description-content">
                    {{DESCRIPTION}}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Image gallery
        document.querySelectorAll('.thumbnail').forEach(thumb => {
            thumb.addEventListener('click', function() {
                const mainImg = document.querySelector('.main-image');
                mainImg.src = this.src;
                document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
            });
        });
    </script>
</body>
</html>
'''
    
    def generate(self, listing_data: Dict, image_paths: List[str] = None) -> str:
        """
        Generate HTML preview
        
        Args:
            listing_data: Dictionary with listing details
            image_paths: Optional list of local image paths
            
        Returns:
            HTML string
        """
        html_content = self.template
        
        # Title
        title = html.escape(listing_data.get('title', 'Untitled Listing'))
        html_content = html_content.replace('{{TITLE}}', title)
        
        # Price
        price = listing_data.get('price', '0.00')
        html_content = html_content.replace('{{PRICE}}', str(price))
        
        # Condition
        condition = listing_data.get('condition', 'Used')
        condition_display = condition.replace('_', ' ').title()
        html_content = html_content.replace('{{CONDITION}}', condition_display)
        
        # Images
        main_image_html = '<div class="main-image" style="display:flex;align-items:center;justify-content:center;color:#999;">No Image</div>'
        thumbnails_html = ''
        
        if image_paths:
            # Convert local images to base64
            images_b64 = []
            for path in image_paths[:8]:  # Max 8 images
                try:
                    with open(path, 'rb') as f:
                        data = base64.b64encode(f.read()).decode()
                        ext = Path(path).suffix.lower()
                        mime = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png'
                        images_b64.append(f'data:{mime};base64,{data}')
                except:
                    pass
            
            if images_b64:
                main_image_html = f'<img class="main-image" src="{images_b64[0]}" alt="Product image">'
                
                for i, img in enumerate(images_b64):
                    active = 'active' if i == 0 else ''
                    thumbnails_html += f'<img class="thumbnail {active}" src="{img}" alt="Thumbnail {i+1}">'
        
        elif listing_data.get('image_urls'):
            # Use remote URLs
            urls = listing_data['image_urls']
            if urls:
                main_image_html = f'<img class="main-image" src="{urls[0]}" alt="Product image">'
                for i, url in enumerate(urls[:8]):
                    active = 'active' if i == 0 else ''
                    thumbnails_html += f'<img class="thumbnail {active}" src="{url}" alt="Thumbnail {i+1}">'
        
        html_content = html_content.replace('{{MAIN_IMAGE}}', main_image_html)
        html_content = html_content.replace('{{THUMBNAILS}}', thumbnails_html)
        
        # Shipping
        shipping = listing_data.get('shipping_info', 'Standard shipping available')
        html_content = html_content.replace('{{SHIPPING_INFO}}', html.escape(str(shipping)))
        
        # Item specifics
        specifics = listing_data.get('item_specifics', {})
        specifics_html = ''
        for key, value in specifics.items():
            specifics_html += f'''
                <div class="specific-item">
                    <span class="specific-label">{html.escape(str(key))}</span>
                    <span class="specific-value">{html.escape(str(value))}</span>
                </div>
            '''
        
        if not specifics_html:
            specifics_html = '<div style="color:#888;">No item specifics set</div>'
        
        html_content = html_content.replace('{{SPECIFICS}}', specifics_html)
        
        # Description (already HTML, don't escape)
        description = listing_data.get('description', '<p>No description provided.</p>')
        html_content = html_content.replace('{{DESCRIPTION}}', description)
        
        return html_content
    
    def save_preview(self, listing_data: Dict, output_path: str, 
                    image_paths: List[str] = None) -> Path:
        """
        Generate and save preview HTML file
        
        Args:
            listing_data: Listing data dictionary
            output_path: Path to save HTML file
            image_paths: Optional image paths
            
        Returns:
            Path to saved file
        """
        html_content = self.generate(listing_data, image_paths)
        
        output = Path(output_path)
        output.write_text(html_content, encoding='utf-8')
        
        return output


# Test
if __name__ == "__main__":
    print("Testing Preview Generator...")
    
    generator = PreviewGenerator()
    
    # Test data
    listing = {
        'title': 'Xerox Sensor Part ABC123 - Excellent Condition',
        'price': '45.99',
        'condition': 'USED_EXCELLENT',
        'shipping_info': 'Free shipping, ships within 1 business day',
        'item_specifics': {
            'Brand': 'Xerox',
            'Model': 'ABC123',
            'Type': 'Sensor',
            'Condition': 'Used - Excellent',
        },
        'description': '''
            <h2>Product Overview</h2>
            <p>This is a genuine Xerox sensor in excellent used condition.</p>
            
            <h2>Features</h2>
            <ul>
                <li>Original Xerox part</li>
                <li>Tested and working</li>
                <li>Clean and ready to install</li>
            </ul>
            
            <h2>Shipping</h2>
            <p>Ships within 24 hours of payment.</p>
        '''
    }
    
    # Generate preview
    html_output = generator.generate(listing)
    
    # Save to temp file
    output_path = Path(__file__).parent / "test_preview.html"
    output_path.write_text(html_output, encoding='utf-8')
    
    print(f"Preview saved to: {output_path}")
    print(f"Preview size: {len(html_output)} bytes")
    
    # Cleanup
    # output_path.unlink()
    
    print("\n✅ Preview Generator working!")
