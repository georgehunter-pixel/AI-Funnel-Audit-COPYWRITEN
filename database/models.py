from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    subscription_tier = Column(String(50), default="free")
    subscription_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    audits = relationship("Audit", back_populates="user")

class Audit(Base):
    __tablename__ = "audits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    url = Column(String(500), nullable=False)
    audit_type = Column(String(50), default="basic")  # basic, full, premium
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    overall_score = Column(Float, nullable=True)
    estimated_revenue_loss = Column(Float, nullable=True)
    issues_count = Column(Integer, default=0)
    results = Column(JSON, nullable=True)
    report_url = Column(String(500), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", back_populates="audits")
    pages = relationship("SitePage", back_populates="audit")
    interaction_tests = relationship("InteractionTest", back_populates="audit")

class SitePage(Base):
    __tablename__ = "site_pages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=False)
    url = Column(String(500), nullable=False)
    page_type = Column(String(50), nullable=True)  # landing, product, checkout, etc.
    title = Column(String(500), nullable=True)
    
    # Performance metrics
    load_time = Column(Float, nullable=True)
    mobile_score = Column(Integer, nullable=True)
    accessibility_score = Column(Integer, nullable=True)
    seo_score = Column(Integer, nullable=True)
    
    # Content analysis
    word_count = Column(Integer, nullable=True)
    image_count = Column(Integer, nullable=True)
    link_count = Column(Integer, nullable=True)
    form_count = Column(Integer, nullable=True)
    
    # Issues and metadata
    issues = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    screenshot_url = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    audit = relationship("Audit", back_populates="pages")
    interaction_tests = relationship("InteractionTest", back_populates="page")

class InteractionTest(Base):
    __tablename__ = "interaction_tests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("site_pages.id"), nullable=False)
    
    test_type = Column(String(50), nullable=False)  # button_click, form_submit, navigation
    element_selector = Column(String(500), nullable=True)
    element_text = Column(String(500), nullable=True)
    
    # Test results
    success = Column(Boolean, nullable=False)
    response_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    screenshot_url = Column(String(500), nullable=True)
    
    # Additional data
    test_data = Column(JSON, nullable=True)  # Form data, click coordinates, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    audit = relationship("Audit", back_populates="interaction_tests")
    page = relationship("SitePage", back_populates="interaction_tests")

class AuditIssue(Base):
    __tablename__ = "audit_issues"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id = Column(UUID(as_uuid=True), ForeignKey("audits.id"), nullable=False)
    page_id = Column(UUID(as_uuid=True), ForeignKey("site_pages.id"), nullable=True)
    
    category = Column(String(50), nullable=False)  # performance, conversion, mobile, seo, trust
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # critical, high, medium, low
    recommendation = Column(Text, nullable=False)
    
    # Impact scoring
    impact_score = Column(Float, nullable=False)
    revenue_impact = Column(Float, nullable=True)
    
    # Evidence
    screenshot_url = Column(String(500), nullable=True)
    element_selector = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    stripe_subscription_id = Column(String(100), unique=True, nullable=True)
    stripe_customer_id = Column(String(100), nullable=True)
    
    plan_name = Column(String(50), nullable=False)  # free, basic, premium
    status = Column(String(50), nullable=False)  # active, canceled, past_due
    
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    
    # Usage tracking
    audits_used = Column(Integer, default=0)
    audits_limit = Column(Integer, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class IndustryBenchmark(Base):
    __tablename__ = "industry_benchmarks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    industry = Column(String(100), nullable=False)
    
    # Performance benchmarks
    avg_load_time = Column(Float, nullable=False)
    avg_mobile_score = Column(Float, nullable=False)
    avg_conversion_rate = Column(Float, nullable=False)
    
    # Issue frequency
    common_issues = Column(JSON, nullable=True)
    
    # Scoring weights
    performance_weight = Column(Float, default=0.25)
    conversion_weight = Column(Float, default=0.35)
    mobile_weight = Column(Float, default=0.20)
    seo_weight = Column(Float, default=0.20)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)