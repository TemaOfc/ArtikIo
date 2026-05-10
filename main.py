from server.app import run_server
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

if __name__ == '__main__':
    local_ip = get_local_ip()

    print("=" * 50)
    print("ArtikIO - Онлайн игра в рисование")
    print("=" * 50)
    print(f"Локальный адрес: http://{local_ip}:5000")
    print(f"Localhost: http://127.0.0.1:5000")
    print("Браузер откроется автоматически...")
    print("=" * 50)
    print("Другие устройства в локальной сети могут")
    print(f"подключиться по адресу: http://{local_ip}:5000")
    print("=" * 50)

    run_server(host='0.0.0.0', port=5000, debug=False)
