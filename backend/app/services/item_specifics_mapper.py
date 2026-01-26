"""
Item Specifics Mapper for eBay Draft Commander
Maps AI research data to eBay item specifics for improved search ranking.
"""
from typing import Dict, List, Optional, Any


class ItemSpecificsMapper:
    """
    Maps research data from AI analyzer to eBay item specifics.
    
    eBay's Best Match algorithm heavily weights complete item specifics.
    This mapper ensures maximum data is extracted and formatted correctly.
    """
    
    # Common eBay item specific field names
    STANDARD_FIELDS = {
        'brand': 'Brand',
        'mpn': 'MPN',
        'model': 'Model',
        'type': 'Type',
        'compatible_brand': 'Compatible Brand',
        'compatible_model': 'Compatible Model',
        'condition': 'Condition',
        'country_of_manufacture': 'Country/Region of Manufacture',
        'upc': 'UPC',
        'ean': 'EAN',
    }
    
    # Industrial/B2B specific fields
    INDUSTRIAL_FIELDS = {
        'voltage': 'Voltage',
        'wattage': 'Wattage',
        'amperage': 'Amperage',
        'capacity': 'Capacity',
        'interface': 'Interface',
        'form_factor': 'Form Factor',
        'speed': 'Speed',
        'color': 'Color',
        'material': 'Material',
        'unit_type': 'Unit Type',
        'unit_quantity': 'Unit Quantity',
    }
    
    # Printing equipment specific fields (Xerox, etc.)
    PRINTING_FIELDS = {
        'page_yield': 'Page Yield',
        'printer_type': 'Printer Type',
        'printing_technology': 'Printing Technology',
        'compatible_printer_brand': 'Compatible Printer Brand',
        'compatible_printer_model': 'Compatible Printer Model',
    }
    
    # Server/IT equipment specific fields
    SERVER_FIELDS = {
        'memory_size': 'Memory Size',
        'memory_type': 'Memory Type',
        'storage_capacity': 'Storage Capacity',
        'storage_type': 'Storage Type',
        'processor_type': 'Processor Type',
        'number_of_ports': 'Number of Ports',
        'network_type': 'Network Type',
        'rack_units': 'Rack Units',
    }
    
    # Broadcast equipment specific fields
    BROADCAST_FIELDS = {
        'video_format': 'Video Format',
        'audio_format': 'Audio Format',
        'connector_type': 'Connector Type',
        'signal_type': 'Signal Type',
        'resolution': 'Resolution',
        'frame_rate': 'Frame Rate',
    }
    
    def __init__(self):
        # Combine all field mappings
        self.all_fields = {
            **self.STANDARD_FIELDS,
            **self.INDUSTRIAL_FIELDS,
            **self.PRINTING_FIELDS,
            **self.SERVER_FIELDS,
            **self.BROADCAST_FIELDS,
        }
    
    def map_research_to_specifics(self, research_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Map AI research data to eBay item specifics.
        
        Args:
            research_data: Output from AIAnalyzer.analyze_with_research()
            
        Returns:
            Dict of eBay item specific name -> value
        """
        specifics = {}
        
        # Extract identification fields
        ident = research_data.get('identification', {})
        if ident.get('brand'):
            specifics['Brand'] = ident['brand']
        if ident.get('mpn'):
            specifics['MPN'] = ident['mpn']
        if ident.get('model'):
            specifics['Model'] = ident['model']
        if ident.get('product_type'):
            specifics['Type'] = ident['product_type']
            
        # Map compatible systems
        compatible = ident.get('compatible_systems', [])
        if compatible:
            # Use first compatible system for eBay field
            specifics['Compatible Model'] = ', '.join(compatible[:3])
            # Extract brand from first compatible system
            if compatible[0]:
                brand_parts = compatible[0].split()
                if brand_parts:
                    specifics['Compatible Brand'] = brand_parts[0]
        
        # Extract origin fields
        origin = research_data.get('origin', {})
        if origin.get('country_of_manufacture'):
            specifics['Country/Region of Manufacture'] = origin['country_of_manufacture']
        
        # Extract technical specifications
        specs = research_data.get('specifications', {})
        tech_specs = specs.get('technical_specs', {})
        
        # Map technical specs to eBay fields
        spec_mapping = {
            'capacity': 'Capacity',
            'speed': 'Speed',
            'interface': 'Interface',
            'voltage': 'Voltage',
            'form_factor': 'Form Factor',
        }
        
        for key, ebay_field in spec_mapping.items():
            value = tech_specs.get(key)
            if value and value.lower() not in ['null', 'none', 'n/a']:
                specifics[ebay_field] = str(value)
        
        # Add color if available
        if specs.get('color'):
            specifics['Color'] = specs['color']
        
        # Extract from research data (Google Search results)
        research = research_data.get('research', {})
        if research.get('researched'):
            research_specs = research.get('specifications', {})
            
            # Map research specs that aren't already filled
            for key, value in research_specs.items():
                if value and isinstance(value, str):
                    # Convert key to title case for eBay
                    ebay_key = key.replace('_', ' ').title()
                    if ebay_key not in specifics:
                        specifics[ebay_key] = value
            
            # Add alternative part numbers as custom specific
            alt_parts = research.get('alternative_part_numbers', [])
            if alt_parts:
                specifics['Alternative Part Number'] = ', '.join(alt_parts[:3])
        
        
        # --- BOOK MODE MAPPING ---
        book_data = research_data.get('book_metadata')
        if book_data and book_data.get('success'):
            # Standard Book Specifics
            specifics['Author'] = ', '.join(book_data.get('authors', []))
            specifics['Publisher'] = book_data.get('publisher', '')
            specifics['Publication Year'] = book_data.get('publishedDate', '')[:4]
            specifics['Book Title'] = book_data.get('title', '')
            specifics['Topic'] = 'Computers' # Default, could extract from categories
            specifics['Language'] = 'English' # Default, could infer
            specifics['Format'] = 'Paperback' # Default assumption
            
            # Map categories to Genre/Subject
            categories = book_data.get('categories', [])
            if categories:
                specifics['Genre'] = categories[0]
            
            # Identifiers
            if book_data.get('isbn'):
                formatted_isbn = book_data['isbn']
                # If 13 digit, try to map to both ISBN-13 and EAN
                if len(formatted_isbn) == 13:
                    specifics['ISBN'] = formatted_isbn
                    specifics['EAN'] = formatted_isbn
                else:
                    specifics['ISBN'] = formatted_isbn
            
            # Add page count if valid
            if book_data.get('pageCount'):
                specifics['Number of Pages'] = str(book_data['pageCount'])

            return specifics
        # --- END BOOK MODE ---

        return specifics
    
    def generate_seo_title(self, research_data: Dict[str, Any], max_length: int = 80) -> str:
        """
        Generate SEO-optimized title for eBay.
        
        Formula: [Brand] [MPN] [Product Type] [Top 2 Compatible] [Condition Tag]
        
        B2B buyers search by part number, so MPN comes early.
        """
        parts = []
        
        ident = research_data.get('identification', {})
        condition = research_data.get('condition', {})
        
        # Brand (required)
        if ident.get('brand'):
            parts.append(ident['brand'])
        
        # MPN (critical for B2B search)
        if ident.get('mpn'):
            parts.append(ident['mpn'])
        
        # Product type
        if ident.get('product_type'):
            parts.append(ident['product_type'])
        
        # Compatible systems (first 2, shortened)
        compatible = ident.get('compatible_systems', [])
        if compatible:
            # Extract just model names without brand prefix
            short_compat = []
            for sys in compatible[:2]:
                # Remove brand prefix if present
                sys_parts = sys.split()
                if len(sys_parts) > 1 and sys_parts[0] == ident.get('brand'):
                    short_compat.append(' '.join(sys_parts[1:]))
                else:
                    short_compat.append(sys)
            parts.append(' '.join(short_compat))
        
        # Condition tag
        if condition.get('is_nos'):
            parts.append('NOS')
        elif condition.get('state'):
            state = condition['state']
            if 'New' in state:
                parts.append('NEW')
        
        # Build title, respecting max length
        title = ' '.join(parts)
        
        # Truncate if needed, but keep complete words
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0]
        

        # --- BOOK TITLE LOGIC ---
        if research_data.get('analysis_mode') == 'book_scan':
            book = research_data.get('book_metadata', {})
            title = book.get('title', '')
            authors = ', '.join(book.get('authors', []))
            year = book.get('publishedDate', '')[:4]
            isbn = book.get('isbn', '')
            
            # Format: Title by Author (Year) ISBN
            seo_title = f"{title} by {authors}"
            if year:
                seo_title += f" ({year})"
            
            # Truncate before adding ISBN if needed
            remaining = max_length - len(seo_title) - len(isbn) - 2
            if remaining < 0:
                seo_title = seo_title[:max_length - len(isbn) - 2]
                
            if isbn:
                seo_title += f" {isbn}"
                
            return seo_title
        # --- END BOOK TITLE LOGIC ---

        return title
    
    def get_condition_id(self, condition_data: Dict[str, Any]) -> int:
        """
        Map condition data to eBay condition ID.
        
        eBay Condition IDs:
        - 1000: New
        - 1500: New (Other)
        - 1750: New with defects
        - 2000: Certified Refurbished
        - 2500: Seller Refurbished
        - 3000: Used
        - 4000: Very Good
        - 5000: Good
        - 6000: Acceptable
        - 7000: For parts or not working
        """
        state = condition_data.get('state', '').lower()
        is_nos = condition_data.get('is_nos', False)
        factory_sealed = condition_data.get('factory_sealed', False)
        
        if factory_sealed and is_nos:
            return 1500  # New (Other) - NOS items
        elif 'new' in state and 'open box' in state:
            return 1500  # New (Other)
        elif 'new' in state:
            return 1000  # New
        elif 'nos' in state:
            return 1500  # New (Other)
        elif 'like new' in state:
            return 3000  # Used (eBay doesn't have used-like new for most categories)
        elif 'good' in state:
            return 5000  # Good
        elif 'acceptable' in state:
            return 6000  # Acceptable
        elif 'parts' in state:
            return 7000  # For parts
        else:
            return 3000  # Default to Used
    
    def generate_condition_description(self, condition_data: Dict[str, Any]) -> str:
        """
        Generate detailed condition description for eBay.
        
        For NOS items, emphasizes original packaging and manufacturing date.
        """
        parts = []
        
        state = condition_data.get('state', 'Used')
        is_nos = condition_data.get('is_nos', False)
        factory_sealed = condition_data.get('factory_sealed', False)
        notes = condition_data.get('notes', '')
        
        if is_nos:
            parts.append("NEW OLD STOCK (NOS):")
            if factory_sealed:
                parts.append("Factory sealed in original packaging.")
            else:
                parts.append("Never used, in original packaging.")
        
        if notes:
            parts.append(notes)
        
        return ' '.join(parts)

    def generate_html_description(self, research_data: Dict[str, Any]) -> str:
        """
        Generate a professional HTML description for NOS/B2B items.
        
        Structure:
        1. Authentic Header (Part Name & Number)
        2. "Technician's Notes" (Authenticity/Condition)
        3. Compatibility Grid
        4. "What's In The Box"
        5. Detailed Specifications
        6. Shipping & Handling Policy
        """
        ident = research_data.get('identification', {})
        condition = research_data.get('condition', {})
        research = research_data.get('research', {})
        specifications = research_data.get('specifications', {})
        
        # Part Identification
        brand = ident.get('brand', 'Unknown Brand')
        mpn = ident.get('mpn', 'N/A')
        model = ident.get('model', '')
        title = ident.get('product_type', 'Industrial Part')
        
        # Authentic Technician Note (Human voice)
        tech_note_parts = []
        if condition.get('is_nos'):
            tech_note_parts.append(f"This is a genuine <b>New Old Stock (NOS)</b> unit from {brand}.")
            if condition.get('factory_sealed'):
                tech_note_parts.append("It is still <b>factory sealed in original packaging</b>.")
            
            # Add date code context if available (often in notes)
            notes = condition.get('notes', '')
            if 'date' in notes.lower() or 'code' in notes.lower():
                 tech_note_parts.append(f"<i>Inspector Note: {notes}</i>")
        else:
             tech_note_parts.append(f"This is a {condition.get('state', 'Used')} unit.")
        
        tech_note_html = ' '.join(tech_note_parts)
        
        # Compatibility List
        compats = ident.get('compatible_systems', [])
        if not compats and research.get('compatible_with'):
             compats = research.get('compatible_with')
             
        compat_html = ""
        if compats:
            rows = ""
            for sys in compats[:6]: # Limit to 6 to keep it clean
                rows += f"<li>{sys}</li>"
            compat_html = f"""
            <div style="background:#f8f9fa; padding:15px; border-radius:5px; margin:20px 0;">
                <h3 style="margin-top:0;">✅ Compatible Systems</h3>
                <ul>{rows}</ul>
            </div>
            """
            
        # Specifications
        specs_html = ""
        tech_specs = specifications.get('technical_specs', {})
        # Merge with research specs
        if research.get('specifications'):
             tech_specs.update(research.get('specifications'))
             
        if tech_specs:
            rows = ""
            for k, v in tech_specs.items():
                if v and str(v).lower() != 'null':
                    label = k.replace('_', ' ').title()
                    rows += f"<tr><td style='padding:8px; border-bottom:1px solid #eee;'><b>{label}</b></td><td style='padding:8px; border-bottom:1px solid #eee;'>{v}</td></tr>"
            
            if rows:
                specs_html = f"""
                <div style="margin:20px 0;">
                    <h3>📋 Technical Specifications</h3>
                    <table style="width:100%; border-collapse:collapse; font-size:14px;">
                        {rows}
                    </table>
                </div>
                """

        # HTML Template
        template = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px; line-height: 1.6; color: #333;">
            
            <!-- Header -->
            <div style="border-bottom: 2px solid #0053a0; padding-bottom: 10px; margin-bottom: 20px;">
                <h1 style="color: #0053a0; margin: 0; font-size: 24px;">{brand} {mpn}</h1>
                <h2 style="color: #666; margin: 5px 0 0; font-size: 18px;">{title} {f'- {model}' if model else ''}</h2>
            </div>
            
            <!-- Technician Note -->
            <div style="background: #eef7ff; border-left: 4px solid #0053a0; padding: 15px; font-size: 15px;">
                <strong>👨‍🔧 Technician's Note:</strong><br>
                {tech_note_html}
            </div>
            
            <!-- Compatibility -->
            {compat_html}
            
            <!-- Specifications -->
            {specs_html}
            
            <!-- What's Included -->
            <div style="margin: 20px 0;">
                <h3>📦 What's In The Box</h3>
                <ul>
                    <li>(1) Genuine {brand} {mpn} {title}</li>
                    <li>Original Factory Packaging</li>
                </ul>
            </div>
            
            <!-- Shipping/Warranty -->
            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; font-size: 13px; color: #555;">
                <p><strong>🚚 Shipping:</strong> Ships same business day if ordered by 2PM EST. Professionally packed with anti-static protection.</p>
                <p><strong>🛡️ Warranty:</strong> 30-Day DOA Guarantee. If it doesn't work for your specific application, return it for a full refund.</p>
            </div>
            
        </div>
        """
        return template



# Convenience function for quick mapping
def map_to_item_specifics(research_data: Dict[str, Any]) -> Dict[str, str]:
    """Quick helper to map research data to item specifics."""
    mapper = ItemSpecificsMapper()
    return mapper.map_research_to_specifics(research_data)


def generate_listing_title(research_data: Dict[str, Any]) -> str:
    """Quick helper to generate SEO title."""
    mapper = ItemSpecificsMapper()
    return mapper.generate_seo_title(research_data)
