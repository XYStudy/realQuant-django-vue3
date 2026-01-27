# 测试WebSocket连接的PowerShell脚本
$uri = "ws://localhost:8000/ws/stock/603069/"

# 创建WebSocket客户端
$webSocket = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationTokenSource

# 连接到WebSocket服务器
Write-Host "正在连接到 $uri..."
$connectTask = $webSocket.ConnectAsync($uri, $cts.Token)

# 等待连接完成
$connectTask.Wait()

if ($webSocket.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
    Write-Host "WebSocket连接成功！"
    
    # 发送开始监控消息
    $message = @{"type" = "start_monitoring"} | ConvertTo-Json
    $buffer = [System.Text.Encoding]::UTF8.GetBytes($message)
    $sendBuffer = New-Object System.ArraySegment[byte] -ArgumentList @(,$buffer)
    $sendTask = $webSocket.SendAsync($sendBuffer, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token)
    $sendTask.Wait()
    Write-Host "已发送开始监控消息"
    
    # 接收消息
    $receiveBuffer = New-Object System.ArraySegment[byte] -ArgumentList @(,($buffer = New-Object byte[](1024)))
    $receiveTask = $webSocket.ReceiveAsync($receiveBuffer, $cts.Token)
    $receiveTask.Wait()
    
    if ($webSocket.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $receivedMessage = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $receiveTask.Result.Count)
        Write-Host "收到消息: $receivedMessage"
    }
    
    # 关闭连接
    $closeTask = $webSocket.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "测试完成", $cts.Token)
    $closeTask.Wait()
    Write-Host "WebSocket连接已关闭"
} else {
    Write-Host "WebSocket连接失败！当前状态: $($webSocket.State)"
}

# 清理资源
$cts.Dispose()
$webSocket.Dispose()
