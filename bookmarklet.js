// eBay Draft Commander - Enhanced Bookmarklet
// This fills the eBay listing form with data from your clipboard

javascript:(async function(){
    // Get clipboard content
    let data;
    try {
        const text = await navigator.clipboard.readText();
        data = JSON.parse(text);
    } catch(e) {
        alert('Could not read clipboard. Make sure you copied listing data from Draft Commander.\n\nError: ' + e.message);
        return;
    }
    
    console.log('📦 eBay Draft Commander - Filling listing...', data);
    
    let filled = [];
    let failed = [];
    
    // Helper to fill a field
    function fillField(selectors, value, name) {
        if (!value) return;
        
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el) {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (el.tagName === 'IFRAME') {
                    // Handle TinyMCE iframe for description
                    try {
                        el.contentDocument.body.innerHTML = value.replace(/\n/g, '<br>');
                    } catch(e) {
                        console.warn('Could not fill iframe:', e);
                    }
                }
                filled.push(name);
                return true;
            }
        }
        failed.push(name);
        return false;
    }
    
    // Fill Title
    fillField([
        'input[name="title"]',
        '#s0-1-1-24-7-\\@keyword-\\@box-\\@input-textbox',
        'input[aria-label*="title"]',
        '#editpane_title input'
    ], data.title, 'Title');
    
    // Fill Price
    fillField([
        'input[name="price"]',
        'input[aria-label*="price"]',
        '#editpane_price input',
        'input[id*="price"]'
    ], data.price, 'Price');
    
    // Fill Description
    fillField([
        '#desc_ifr',
        'textarea[name="description"]',
        '#editpane_item_description textarea',
        'iframe[id*="description"]'
    ], data.description, 'Description');
    
    // Fill Item Specifics
    if (data.item_specifics) {
        for (const [name, value] of Object.entries(data.item_specifics)) {
            // Try to find the input by label text
            const labels = document.querySelectorAll('label, span.ux-textspans');
            
            for (const label of labels) {
                if (label.textContent.includes(name)) {
                    // Find associated input
                    const parent = label.closest('.aspect-entry, .item-specific-row, [class*="aspect"]');
                    if (parent) {
                        const input = parent.querySelector('input, select');
                        if (input) {
                            if (input.tagName === 'SELECT') {
                                // Try to select matching option
                                const options = Array.from(input.options);
                                const match = options.find(o => 
                                    o.text.toLowerCase().includes(value.toLowerCase())
                                );
                                if (match) {
                                    input.value = match.value;
                                } else {
                                    input.value = value;
                                }
                            } else {
                                input.value = value;
                            }
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            filled.push(name);
                            break;
                        }
                    }
                }
            }
        }
    }
    
    // Show result
    const message = `✅ eBay Draft Commander\n\nFilled: ${filled.join(', ')}\n\n${failed.length ? 'Could not find: ' + failed.join(', ') : 'All fields found!'}`;
    alert(message);
})();


// ===========================================
// SIMPLIFIED VERSION (Copy this one-liner as your bookmark URL):
// ===========================================

// javascript:(async()=>{try{const t=await navigator.clipboard.readText(),e=JSON.parse(t);document.querySelectorAll('input[name="title"],input[aria-label*="title"]').forEach(t=>t.value=e.title),document.querySelectorAll('input[name="price"],input[aria-label*="price"]').forEach(t=>t.value=e.price);const i=document.querySelector('#desc_ifr');i&&(i.contentDocument.body.innerHTML=e.description.replace(/\n/g,'<br>')),alert('✅ Filled: Title, Price, Description')}catch(t){alert('Error: '+t.message)}})();
