import threading
import time
from datetime import datetime

class RebalanceScheduler:
    def __init__(self, db_session, nav_service, order_service, alert_service):
        self.db = db_session
        self.nav_service = nav_service
        self.order_service = order_service
        self.alert_service = alert_service

        self.running = False
        self.thread = None

    # ---------------------------------
    # 🔁 START SCHEDULER
    # ---------------------------------
    def start(self, portfolio_id, user_id=None, interval_seconds=300, threshold=0.05, auto_execute=False):
        if self.running:
            return

        self.running = True

        def loop():
            print("🚀 Rebalance Scheduler Started")

            while self.running:
                try:
                    print(f"⏱ Running rebalance check @ {datetime.utcnow()}")

                    result = self.nav_service.auto_rebalance_check(
                        portfolio_id=portfolio_id,
                        order_service=self.order_service,
                        alert_service=self.alert_service,
                        user_id=user_id,
                        threshold=threshold,
                        auto_execute=auto_execute
                    )

                    print("📊 Scheduler Result:", result)

                except Exception as e:
                    print("❌ Scheduler Error:", e)

                time.sleep(interval_seconds)

        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    # ---------------------------------
    # 🛑 STOP SCHEDULER
    # ---------------------------------
    def stop(self):
        self.running = False
        print("🛑 Rebalance Scheduler Stopped")