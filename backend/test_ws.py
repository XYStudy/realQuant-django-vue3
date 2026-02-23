import asyncio
import websockets
import json

async def test_monitor():
    uri = "ws://localhost:8000/ws/stock/603069/"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected")
            
            # Wait for connection established message
            msg = await websocket.recv()
            print(f"Initial message: {msg}")
            
            # Send start monitoring
            await websocket.send(json.dumps({
                "type": "start_monitoring",
                "record_data": False
            }))
            print("Sent start_monitoring")
            
            # Listen for messages
            for i in range(10):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    print(f"Received type: {data.get('type')}")
                    
                    if data.get('type') == 'stock_data':
                        stock_data = data.get('stock_data', {})
                        # print(f"Stock Data keys: {stock_data.keys()}")
                        if 'strategy_info' in stock_data:
                            print(f"Strategy Info: {stock_data['strategy_info']}")
                        else:
                            print("No strategy info in stock_data")
                        
                        # Once we get data, we can stop
                        break
                        
                except asyncio.TimeoutError:
                    print(f"Timeout waiting for message {i}")
                    pass
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_monitor())