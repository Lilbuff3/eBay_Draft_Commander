"""
Backend API endpoint for creating eBay listings from uploaded photos.
Add this route to web_server.py in the _register_routes method.
"""

@self.app.route('/api/listing/create-from-photos', methods=['POST'])
def create_listing_from_photos():
    """Create eBay listing from uploaded photos (mobile-friendly)"""
    try:
        # Get uploaded files
        uploaded_files = []
        for key in request.files:
            if key.startswith('photo'):
                uploaded_files.append(request.files[key])
        
        if not uploaded_files:
            return jsonify({'success': False, 'error': 'No photos uploaded'}), 400
        
        # Get optional metadata
        item_name = request.form.get('itemName', '').strip()
        price = request.form.get('price', '').strip()
        description = request.form.get('description', '').strip()
        
        # Create temporary job folder
        import uuid
        import shutil
        from datetime import datetime
        
        job_id = f"mobile_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        job_folder = Path(self.base_path) / 'inbox' / job_id
        job_folder.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Creating listing from {len(uploaded_files)} uploaded photos", 
                        extra={'job_id': job_id})
        
        # Save uploaded photos to job folder
        for i, file in enumerate(uploaded_files):
            if file and file.filename:
                # Sanitize filename
                ext = Path(file.filename).suffix.lower()
                if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                    ext = '.jpg'
                
                photo_path = job_folder / f"photo_{i+1:02d}{ext}"
                file.save(str(photo_path))
                self.logger.debug(f"Saved photo: {photo_path.name}")
        
        # Create metadata file if user provided info
        if item_name or price or description:
            metadata = {}
            if item_name:
                metadata['title_hint'] = item_name
            if price:
                try:
                    metadata['price'] = float(price)
                except ValueError:
                    pass
            if description:
                metadata['description_hint'] = description
            
            metadata_file = job_folder / 'metadata.json'
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        # Process the listing using existing pipeline
        from create_from_folder import create_listing_from_folder
        
        result = create_listing_from_folder(
            str(job_folder),
            price=float(price) if price else None
        )
        
        if result:
            self.logger.info(f"Listing created successfully from mobile upload", 
                           extra={'job_id': job_id, 'result': result})
            
            return jsonify({
                'success': True,
                'listingId': result if isinstance(result, str) and result.startswith('2') else None,
                'offerId': result if isinstance(result, str) and not result.startswith('2') else None,
                'jobId': job_id,
                'photosProcessed': len(uploaded_files)
            })
        else:
            # Clean up folder on failure
            if job_folder.exists():
                shutil.rmtree(job_folder)
            
            return jsonify({
                'success': False,
                'error': 'Failed to create listing'
            }), 500
            
    except FileNotFoundError as e:
        self.logger.error(f"File not found during photo upload: {e}")
        return jsonify({'success': False, 'error': 'Upload processing failed'}), 500
        
    except ImportError as e:
        self.logger.error(f"create_from_folder module not available: {e}")
        return jsonify({'success': False, 'error': 'Listing creation not configured'}), 500
        
    except Exception as e:
        self.logger.exception("Error creating listing from photos")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
