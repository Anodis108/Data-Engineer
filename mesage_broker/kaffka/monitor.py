import time
import psutil
import threading
import os


class ResourceMonitorThread(threading.Thread):
    def __init__(self, interval=0.2):
        super().__init__()
        self.interval = interval
        self._running = True
        self.process = psutil.Process(os.getpid())
        self.cpu_list = []
        self.ram_list = []
        self.daemon = True
        
    def run(self):
        while self._running:
            cpu = self.process.cpu_percent(interval=1)
            ram = self.process.memory_info().rss / (1024 * 1024)
            self.cpu_list.append(cpu)
            self.ram_list.append(ram)
            time.sleep(self.interval)
            
    def stop(self):
        self._running = False
        
    def get_average_usage(self):
        avg_cpu = sum(self.cpu_list) / len(self.cpu_list) if self.cpu_list else 0.0
        avg_ram = sum(self.ram_list) / len(self.ram_list) if self.ram_list else 0.0
        return avg_cpu, avg_ram


# Ví dụ dùng độc lập:
if __name__ == '__main__':
    print("🟢 Bắt đầu theo dõi CPU/RAM...")
    monitor = ResourceMonitorThread(interval=0.2)
    monitor.start()

    try:
        for i in range(5):
            print(f"⌛ Đang làm việc... {i+1}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        monitor.join()

        avg_cpu, avg_ram = monitor.get_average_usage()
        print(f"\n📊 CPU trung bình: {avg_cpu:.2f}% | RAM trung bình: {avg_ram:.2f} MB")
