import { useState } from 'react'

export default function Test() {
    const [count, setCount] = useState(0)
    return (
        <div style={{ padding: '20px', textAlign: 'center' }}>
            <h1>Test Component</h1>
            <p>Count: {count}</p>
            <button onClick={() => setCount(c => c + 1)}>Increment</button>
        </div>
    )
}
