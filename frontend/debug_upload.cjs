
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    // Capture console logs
    page.on('console', msg => console.log('BROWSER LOG:', msg.text()));

    // Capture network failures
    page.on('requestfailed', request => {
        console.log(`NETWORK FAIL: ${request.url()} - ${request.failure().errorText}`);
    });

    page.on('response', async response => {
        if (response.url().includes('/upload')) {
            console.log(`UPLOAD STATUS: ${response.status()}`);
            if (response.status() >= 400) {
                try {
                    const text = await response.text();
                    console.log(`UPLOAD ERROR BODY: ${text}`);
                } catch (e) {
                    console.log('Could not read error body');
                }
            } else {
                try {
                    const text = await response.text();
                    console.log(`UPLOAD SUCCESS BODY: ${text}`);
                } catch (e) {
                    console.log('Could not read success body');
                }
            }
        }
    });

    try {
        console.log('Navigating to dashboard...');
        await page.goto('http://localhost:5175', { waitUntil: 'networkidle0' });

        // specific for this app, wait for the upload input
        console.log('Waiting for file input...');
        const fileInput = await page.waitForSelector('#file-upload');

        // Create a dummy image
        const imagePath = path.join(__dirname, 'test_image.png');
        // Simple 1x1 pixel PNG
        const buffer = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');
        fs.writeFileSync(imagePath, buffer);

        console.log('Uploading image...');
        // Ensure file input is cleared first? No, puppeteer handles it.
        await fileInput.uploadFile(imagePath);

        console.log('Waiting for upload result...');

        // Wait for network idle or success/failure
        try {
            await page.waitForResponse(response => response.url().includes('/upload'), { timeout: 10000 });
            console.log('Upload request completed.');
        } catch (e) {
            console.log('Timeout waiting for upload response');
        }

    } catch (error) {
        console.error('TEST ERROR:', error);
    } finally {
        await browser.close();
    }
})();
