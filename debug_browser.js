
const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--ignore-certificate-errors']
    });
    const page = await browser.newPage();

    // Capture console logs
    const logs = [];
    page.on('console', msg => {
        const logEntry = `[${msg.type()}] ${msg.text()}`;
        logs.push(logEntry);
        console.log(logEntry);
    });

    try {
        console.log('Navigating to http://localhost:5175/ ...');
        await page.goto('http://localhost:5175/', { waitUntil: 'networkidle2', timeout: 30000 });

        // Wait a bit for React to mount
        await new Promise(r => setTimeout(r, 2000));

        const content = await page.content();
        fs.writeFileSync('debug_content.html', content);

        await page.screenshot({ path: 'debug_screenshot.png', fullPage: true });

        const bodyText = await page.evaluate(() => document.body.innerText);
        console.log('Body Text Length:', bodyText.length);

        fs.writeFileSync('debug_logs.txt', logs.join('\n'));
        console.log('Debug data saved to debug_content.html, debug_screenshot.png, and debug_logs.txt');

    } catch (err) {
        console.error('Error during navigation:', err);
        fs.writeFileSync('debug_error.txt', err.stack);
    } finally {
        await browser.close();
    }
})();
