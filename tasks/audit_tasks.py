from celery import current_task
from celery_app import celery_app
from sqlalchemy.orm import Session
from database.database import SessionLocal
from database.models import Audit, User
from services.crawler_service import CrawlerService
from services.interaction_service import InteractionService
from services.report_service import ReportService
from tasks.email_tasks import send_audit_completion_email
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_comprehensive_audit(self, audit_id: str):
    """Run a comprehensive website audit"""
    db = SessionLocal()
    
    try:
        # Get audit from database
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if not audit:
            raise Exception(f"Audit {audit_id} not found")
        
        # Update status to processing
        audit.status = "processing"
        audit.progress = 5
        db.commit()
        
        # Update task progress
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 5, "message": "Starting audit..."}
        )
        
        # Phase 1: Crawl website
        logger.info(f"Starting crawl for audit {audit_id}")
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 10, "message": "Crawling website..."}
        )
        
        crawler_service = CrawlerService()
        sitemap = await crawler_service.crawl_website(audit.url)
        
        audit.progress = 30
        db.commit()
        
        # Phase 2: Test interactions
        logger.info(f"Testing interactions for audit {audit_id}")
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 30, "message": "Testing interactions..."}
        )
        
        interaction_service = InteractionService()
        interaction_results = await interaction_service.test_all_interactions(sitemap)
        
        audit.progress = 60
        db.commit()
        
        # Phase 3: Analyze performance
        logger.info(f"Analyzing performance for audit {audit_id}")
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 60, "message": "Analyzing performance..."}
        )
        
        performance_results = await interaction_service.analyze_performance(sitemap)
        
        audit.progress = 80
        db.commit()
        
        # Phase 4: Generate report
        logger.info(f"Generating report for audit {audit_id}")
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 80, "message": "Generating report..."}
        )
        
        report_service = ReportService()
        report_data = await report_service.generate_comprehensive_report(
            sitemap, interaction_results, performance_results
        )
        
        # Save results
        audit.results = report_data
        audit.overall_score = report_data.get("overall_score", 0)
        audit.estimated_revenue_loss = report_data.get("estimated_revenue_loss", 0)
        audit.issues_count = len(report_data.get("issues", []))
        audit.status = "completed"
        audit.progress = 100
        audit.completed_at = datetime.utcnow()
        
        db.commit()
        
        # Send completion email
        user = db.query(User).filter(User.id == audit.user_id).first()
        if user:
            send_audit_completion_email.delay(user.email, audit_id)
        
        logger.info(f"Audit {audit_id} completed successfully")
        
        return {
            "status": "completed",
            "audit_id": audit_id,
            "results": report_data
        }
        
    except Exception as e:
        logger.error(f"Audit {audit_id} failed: {str(e)}")
        
        # Update audit status to failed
        audit = db.query(Audit).filter(Audit.id == audit_id).first()
        if audit:
            audit.status = "failed"
            audit.error_message = str(e)
            db.commit()
        
        # Update task state
        current_task.update_state(
            state="FAILURE",
            meta={"error": str(e), "audit_id": audit_id}
        )
        
        raise e
        
    finally:
        db.close()

@celery_app.task
def cleanup_old_audits():
    """Clean up old audit data"""
    db = SessionLocal()
    
    try:
        # Delete audits older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        old_audits = db.query(Audit).filter(
            Audit.created_at < cutoff_date,
            Audit.status.in_(["completed", "failed"])
        ).all()
        
        for audit in old_audits:
            db.delete(audit)
        
        db.commit()
        logger.info(f"Cleaned up {len(old_audits)} old audits")
        
    except Exception as e:
        logger.error(f"Failed to cleanup old audits: {str(e)}")
        db.rollback()
        
    finally:
        db.close()

@celery_app.task
def retry_failed_audits():
    """Retry failed audits with retry count < 3"""
    db = SessionLocal()
    
    try:
        failed_audits = db.query(Audit).filter(
            Audit.status == "failed",
            Audit.retry_count < 3
        ).all()
        
        for audit in failed_audits:
            audit.retry_count += 1
            audit.status = "pending"
            audit.error_message = None
            db.commit()
            
            # Requeue the audit
            run_comprehensive_audit.delay(str(audit.id))
            
        logger.info(f"Requeued {len(failed_audits)} failed audits")
        
    except Exception as e:
        logger.error(f"Failed to retry audits: {str(e)}")
        
    finally:
        db.close()