from modules.analytics.universe_job_registry import UniverseJobRegistry
from modules.analytics.universe_execution_queue import UniverseExecutionQueue
from modules.analytics.universe_workload_balancer import UniverseWorkloadBalancer
from modules.analytics.universe_runtime_controller import UniverseRuntimeController
from modules.analytics.intelligent_analytics_scheduler import IntelligentAnalyticsScheduler
from modules.analytics.universe_analytics_orchestrator import UniverseAnalyticsOrchestrator
from modules.analytics.analytics_resource_governor import AnalyticsResourceGovernor
from modules.analytics.autonomous_analytics_optimizer import AutonomousAnalyticsOptimizer
from modules.analytics.analytics_test_harness import run_analytics_validation


DB_PATH = "data/analytics_fabric_test.db"


registry = UniverseJobRegistry(db_path=DB_PATH)
queue = UniverseExecutionQueue(registry=registry, db_path=DB_PATH)
balancer = UniverseWorkloadBalancer()
runtime = UniverseRuntimeController(
    registry=registry,
    queue=queue,
    balancer=balancer,
    db_path=DB_PATH,
)

scheduler = IntelligentAnalyticsScheduler(registry=registry)

orchestrator = UniverseAnalyticsOrchestrator(
    registry=registry,
    scheduler=scheduler,
    execution_queue=queue,
    workload_balancer=balancer,
    runtime_controller=runtime,
)

governor = AnalyticsResourceGovernor()
optimizer = AutonomousAnalyticsOptimizer()

runtime.start()
runtime.register_worker(worker_id="test_worker_1", capacity=10)

suite = run_analytics_validation(
    registry=registry,
    queue=queue,
    scheduler=scheduler,
    balancer=balancer,
    runtime_controller=runtime,
    orchestrator=orchestrator,
    governor=governor,
    optimizer=optimizer,
)

print("\n=== ANALYTICS FABRIC VALIDATION ===")
print(suite.summary())

for result in suite.results:
    print(f"{result.status:5} | {result.test_name:15} | {result.message}")
    if result.status == "FAIL":
        print(result.metadata.get("traceback", ""))