from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    user_id    = Column(String, primary_key=True, default=generate_uuid)
    username   = Column(String, nullable=False, unique=True)
    password   = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    projects   = relationship("Project", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    project_id    = Column(String, primary_key=True, default=generate_uuid)
    user_id       = Column(String, ForeignKey("users.user_id"), nullable=False)
    name          = Column(String, nullable=False)
    repo_url      = Column(String)
    framework     = Column(String)
    port          = Column(Integer, default=8000)
    start_command = Column(String)
    subdomain     = Column(String, unique=True)
    status        = Column(String, default="pending")
    env_vars      = Column(JSON, default=dict, nullable=False, server_default="{}")
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user        = relationship("User", back_populates="projects")
    builds      = relationship("Build", back_populates="project")
    deployments = relationship("Deployment", back_populates="project")
    domain      = relationship("Domain", back_populates="project", uselist=False)


class Build(Base):
    __tablename__ = "builds"

    build_id       = Column(String, primary_key=True, default=generate_uuid)
    project_id     = Column(String, ForeignKey("projects.project_id"), nullable=False)
    status         = Column(String, default="queued")
    image_tag      = Column(String)
    log_output     = Column(Text)
    log_expires_at = Column(DateTime)
    started_at     = Column(DateTime)
    finished_at    = Column(DateTime)
    created_at     = Column(DateTime, default=datetime.utcnow)

    project     = relationship("Project", back_populates="builds")
    deployments = relationship("Deployment", back_populates="build")

class Deployment(Base):
    __tablename__ = "deployments"

    deployment_id = Column(String, primary_key=True, default=generate_uuid)
    project_id    = Column(String, ForeignKey("projects.project_id"), nullable=False)
    build_id      = Column(String, ForeignKey("builds.build_id"), nullable=False)
    container_id  = Column(String)
    status        = Column(String, default="pending")
    deployed_at   = Column(DateTime)
    created_at    = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="deployments")
    build   = relationship("Build", back_populates="deployments")


class Domain(Base):
    __tablename__ = "domains"

    domain_id  = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False, unique=True)
    subdomain  = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="domain")