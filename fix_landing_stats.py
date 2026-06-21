with open('landing.html', 'r') as f:
    content = f.read()

# หาและแก้ฟังก์ชัน updateStats
old_func = """function updateStats() {
        console.log('Updating stats...');
        fetch(NODE_URL + '/chain')
            .then(res => {
                console.log('Response status:', res.status);
                return res.json();
            })
            .then(blocks => {
                console.log('Blocks loaded:', blocks.length);
                document.getElementById('stat-blocks').textContent = blocks.length;"""

new_func = """function updateStats() {
        console.log('Updating stats...');
        fetch(NODE_URL + '/chain')
            .then(res => {
                console.log('Response status:', res.status);
                return res.json();
            })
            .then(data => {
                // Handle both array and object responses
                const blocks = Array.isArray(data) ? data : (data.chain || []);
                console.log('Blocks loaded:', blocks.length);
                document.getElementById('stat-blocks').textContent = blocks.length;"""

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('landing.html', 'w') as f:
        f.write(content)
    print("✅ Fixed updateStats function")
else:
    print("⚠️ Pattern not found - need manual fix")
