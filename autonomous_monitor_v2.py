from integrated_guard_v3 import IntegratedGuardV3
import requests, time, json, os
from datetime import datetime

class AutonomousMonitorV2(IntegratedGuardV3):
    def __init__(self, target_address, check_interval=60):
        super().__init__()
        self.target_address = target_address.lower()
        self.check_interval = check_interval
        self.last_known_balance = None
        self.last_tx_count = 0  # เพิ่มตัวนับ TX เพื่อตรวจจับธุรกรรมใหม่
        self.log_file = "monitor_log.json"
        
    def get_on_chain_data(self):
        """ดึงทั้ง Balance และ TX Count จาก RPC"""
        try:
            # ดึง Balance
            balance_resp = requests.post(
                "https://arbitrum-one.publicnode.com", 
                json={"jsonrpc": "2.0", "method": "eth_getBalance", 
                      "params": [self.target_address, "latest"], "id": 1}, timeout=10
            ).json()
            wei = int(balance_resp.get('result', '0x0'), 16)
            balance = wei / 1e18
            
            # ดึง Transaction Count (Nonce)
            count_resp = requests.post(
                "https://arbitrum-one.publicnode.com", 
                json={"jsonrpc": "2.0", "method": "eth_getTransactionCount", 
                      "params": [self.target_address, "latest"], "id": 2}, timeout=10
            ).json()
            tx_count = int(count_resp.get('result', '0x0'), 16)
            
            return balance, tx_count
        except Exception as e:
            print(f"❌ Data fetch failed: {e}")
            return None, None

    def monitor_loop(self):
        """ลูปการทำงานอัตโนมัติ V2"""
        print(f"🛡️ AUTONOMOUS MONITOR V2 STARTED")
        print(f"   Target: {self.target_address}")
        print(f"   Interval: {self.check_interval}s")
        print(f"   Features: Balance + TX Count Monitoring")
        print(f"   Press Ctrl+C to stop\n")
        
        while True:
            try:
                current_balance, current_tx_count = self.get_on_chain_data()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if current_balance is None:
                    time.sleep(self.check_interval)
                    continue
                
                # ตรวจจับการเปลี่ยนแปลง Balance
                balance_changed = (self.last_known_balance is not None and 
                                 current_balance != self.last_known_balance)
                
                # ตรวจจับ TX ใหม่ (TX Count เพิ่ม = มีธุรกรรมใหม่)
                tx_changed = (current_tx_count > self.last_tx_count)
                
                if balance_changed or tx_changed:
                    change = (current_balance - self.last_known_balance) if self.last_known_balance else 0
                    risk_level = "HIGH" if change < 0 else "LOW"
                    
                    alert = {
                        "timestamp": timestamp,
                        "event": "BALANCE_CHANGE" if balance_changed else "NEW_TX",
                        "previous_balance": self.last_known_balance,
                        "current_balance": current_balance,
                        "change_eth": change,
                        "tx_count_change": current_tx_count - self.last_tx_count if tx_changed else 0,
                        "risk_level": risk_level,
                        "action_required": change < 0 or tx_changed
                    }
                    
                    self._log_alert(alert)
                    self._trigger_advanced_verification(change, tx_changed)
                
                self.last_known_balance = current_balance
                self.last_tx_count = current_tx_count
                
                status = "MONITORING"
                if tx_changed: status = "NEW TX DETECTED"
                elif balance_changed: status = "BALANCE CHANGED"
                
                print(f"[{timestamp}] Balance: {current_balance:.6f} ETH | TX Count: {current_tx_count} | Status: {status}")
                
            except KeyboardInterrupt:
                print("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                print(f"⚠️ Loop error: {e}")
            
            time.sleep(self.check_interval)

    def _trigger_advanced_verification(self, change, has_new_tx):
        """ตรวจสอบขั้นสูงเมื่อมีกิจกรรมใหม่"""
        if has_new_tx:
            claim = f"New transaction detected on {self.target_address}"
            # ในอนาคตสามารถดึง TX Hash ล่าสุดมาตรวจสอบได้
            result = self.verify_with_context(claim, tx_hash=None)
        else:
            claim = f"Balance changed by {change:.6f} ETH without new TX"
            result = self.verify_with_context(claim, tx_hash=None)
        
        print(f"\n🔍 AUTO-VERIFICATION TRIGGERED:")
        print(f"   Claim: {claim}")
        print(f"   Verdict: {result['result']}")
        print(f"   Confidence: {result['confidence']}% | Risk: {result['risk_level']}\n")

    def _log_alert(self, alert):
        """บันทึกเหตุการณ์ลงไฟล์ Log แบบ Atomic"""
        logs = []
        if os.path.exists(self.log_file):
            try: logs = json.loads(open(self.log_file).read())
            except: pass
        
        logs.append(alert)
        tmp = self.log_file + ".tmp"
        with open(tmp, 'w') as f: json.dump(logs, f, indent=2)
        os.replace(tmp, self.log_file)
        print(f"💾 Alert logged: {alert['event']} | Change: {alert.get('change_eth', 0):.6f} ETH")

# === เริ่มระบบเฝ้าระวัง V2 ===
if __name__ == "__main__":
    monitor = AutonomousMonitorV2(
        target_address="0xfb8a6aeb93bc68db75e295cb9b35a84d6753bc61",
        check_interval=30
    )
    monitor.monitor_loop()
