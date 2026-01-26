# eBay Draft Commander - User Manual

Welcome to your daily selling tool. This guide covers how to start your day, process bulk items, and troubleshoot common issues.

## 🌅 Daily Selling Workflow

### 1. Start the Session
Double-click `Start_Selling_Session.bat` on your desktop.
- This will check for updates, run a health check, and launch the dashboard.
- If everything is green, your browser will open to the **Dashboard**.

### 2. Prepare Photos
**Method A: Folder Prep (Traditional)**
1. Transfer photos to your computer.
2. Organize them into folders inside the `inbox` folder:
   ```
   /inbox
     /Nike_Shoes_Sz10/ ...
   ```

**Method B: Direct Mobile Upload (New!)**
1. Open the **Draft Commander** app on your phone.
2. Tap **"Step 1: Add Photos"** or the upload icon.
3. Select photos from your Camera Roll.
4. The app will automatically create a job folder and start processing.
   *No computer transfer required!*

### 3. Bulk Scan (Mobile or Desktop)
**From your Phone:**
1. Scan the QR code in the terminal window.
2. Tap **"Add to Home Screen"** to install the app.
3. Open the app and tap **"Scan 'inbox' Folder"**.

**Result:**
- The app will detect all new folders.
- It will automatically create a Queue Job for each folder.
- AI analysis will begin immediately.

### 4. Review & Create
1. Go to the **Dashboard** (on Desktop for best experience).
2. Click on a job in the **Queue** list.
3. **Verify:**
   - **Title**: Did AI capture the brand/model correctly?
   - **Price**: Check the AI estimate vs. recent solds (Research Tab).
   - **Condition**: Ensure graded correctly.
4. **Create Listing**:
   - Select a Shipping Policy.
   - Click **"Create Listing"**.
   - The item is now a draft in your eBay account!

---

## 📱 Mobile App Tips
- **Connectivity**: Your phone must be on the same Wi-Fi as your computer.
- **PWA**: Using "Add to Home Screen" hides the browser bar, giving you more screen space.
- **Photos**: You can upload photos directly from your phone into a new job using the "Upload" zone if you haven't prepared folders.

---

## 🔧 Troubleshooting

### "System Health Check Failed"
- **API Error**: Your eBay token might have expired. Run `python ebay_auth.py` to re-login.
- **Dependency**: If Python libraries are missing, run `pip install -r requirements.txt`.

### "Scan Inbox" finds nothing
- Ensure your folders are inside `PROJECT_ROOT/inbox`.
- Ensure the folders contain `.jpg`, `.jpeg`, or `.png` images.
- Ensure the folder isn't *already* in the queue (the system prevents duplicates).

### Mobile App won't connect
- Check valid IP address in the terminal output.
- Ensure Windows Firewall isn't blocking Python.
- Confirm phone and PC are on the same network.

---

## 📊 Analytics
Check the **Analytics** tab to see your:
- Total items listed today.
- Estimated potential revenue.
- Sell-through rate of your active inventory.
