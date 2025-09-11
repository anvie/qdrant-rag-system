#!/usr/bin/env python3
"""
Migration script to populate database with metadata for existing Qdrant collections.
This script scans existing collections and creates database records with default configurations.
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from qdrant_client import QdrantClient
from app.core.config import settings
from app.core.database import get_db_session, init_database
from app.models.collection import Collection as CollectionModel
from app.services.embedding_models import get_embedding_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_existing_collections(dry_run: bool = False):
    """
    Migrate existing Qdrant collections to the database.

    Args:
        dry_run: If True, only show what would be migrated without making changes
    """
    logger.info("🔄 Starting collection migration...")

    try:
        # Initialize database if needed
        if not dry_run:
            init_database()

        # Connect to Qdrant
        client = QdrantClient(url=settings.QDRANT_URL)
        logger.info(f"📊 Connected to Qdrant at {settings.QDRANT_URL}")

        # Get all existing collections
        collections_info = client.get_collections()
        logger.info(
            f"🔍 Found {len(collections_info.collections)} existing collections"
        )

        migrated_count = 0
        skipped_count = 0

        with get_db_session() as db:
            for collection_info in collections_info.collections:
                collection_name = collection_info.name
                logger.info(f"📝 Processing collection: {collection_name}")

                # Check if collection already has metadata in database
                existing_meta = (
                    db.query(CollectionModel)
                    .filter(CollectionModel.name == collection_name)
                    .first()
                )

                if existing_meta:
                    logger.info(
                        f"  ⏭️  Skipping {collection_name} - metadata already exists"
                    )
                    skipped_count += 1
                    continue

                # Get collection details from Qdrant
                try:
                    collection_details = client.get_collection(collection_name)
                    vector_config = collection_details.config.params.vectors

                    vector_size = vector_config.size
                    distance_metric = (
                        str(vector_config.distance).lower().replace("distance.", "")
                    )

                    # Convert distance enum to our format
                    distance_map = {
                        "cosine": "cosine",
                        "euclid": "euclidean",
                        "dot": "dot",
                    }
                    distance_metric = distance_map.get(distance_metric, "cosine")

                    logger.info(
                        f"  📐 Vector size: {vector_size}, Distance: {distance_metric}"
                    )

                    # Try to determine embedding model based on vector size
                    embedding_model = determine_embedding_model_by_vector_size(
                        vector_size
                    )
                    logger.info(f"  🤖 Inferred embedding model: {embedding_model}")

                    if dry_run:
                        logger.info(
                            f"  [DRY RUN] Would create metadata for {collection_name}"
                        )
                        logger.info(f"    - Model: {embedding_model}")
                        logger.info(f"    - Vector Size: {vector_size}")
                        logger.info(f"    - Distance: {distance_metric}")
                    else:
                        # Create database record
                        collection_meta = CollectionModel(
                            name=collection_name,
                            embedding_model=embedding_model,
                            vector_size=vector_size,
                            distance_metric=distance_metric,
                            description=f"Migrated from existing Qdrant collection on {datetime.now().strftime('%Y-%m-%d')}",
                            status="unknown",
                            points_count=0,
                            vectors_count=0,
                        )

                        db.add(collection_meta)
                        logger.info(f"  ✅ Created metadata for {collection_name}")

                    migrated_count += 1

                except Exception as e:
                    logger.error(f"  ❌ Failed to process {collection_name}: {e}")
                    continue

            if not dry_run:
                db.commit()
                logger.info("💾 Database changes committed")

        client.close()

        # Summary
        logger.info("📊 Migration Summary:")
        logger.info(f"  - Collections migrated: {migrated_count}")
        logger.info(f"  - Collections skipped: {skipped_count}")
        logger.info(f"  - Total collections: {len(collections_info.collections)}")

        if dry_run:
            logger.info("🔍 This was a dry run - no changes were made")
        else:
            logger.info("✅ Migration completed successfully")

        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def determine_embedding_model_by_vector_size(vector_size: int) -> str:
    """
    Try to determine the most likely embedding model based on vector size.
    """
    # Common vector sizes and their likely models
    size_to_model = {
        384: "all-minilm-l6-v2",  # Sentence Transformers MiniLM
        768: "embeddinggemma:latest",  # BGE Base, Gemma, many others
        1024: "bge-m3:567m",  # BGE Large, BGE-M3
        1536: "text-embedding-ada-002",  # OpenAI (if supported)
        3072: "text-embedding-3-large",  # OpenAI (if supported)
    }

    model = size_to_model.get(vector_size)
    if model:
        logger.info(f"  🎯 Vector size {vector_size} matches known model: {model}")
        return model
    else:
        # Default fallback based on common sizes
        if vector_size <= 400:
            default = "all-minilm-l6-v2"
        elif vector_size <= 800:
            default = "embeddinggemma:latest"
        else:
            default = "bge-m3:567m"

        logger.warning(
            f"  ⚠️  Unknown vector size {vector_size}, using default: {default}"
        )
        return default


def validate_migrated_collections():
    """Validate that all collections have been properly migrated."""
    logger.info("🔍 Validating migrated collections...")

    try:
        client = QdrantClient(url=settings.QDRANT_URL)
        qdrant_collections = {c.name for c in client.get_collections().collections}

        with get_db_session() as db:
            db_collections = {c.name for c in db.query(CollectionModel).all()}

        missing_in_db = qdrant_collections - db_collections
        extra_in_db = db_collections - qdrant_collections

        logger.info(f"📊 Validation Results:")
        logger.info(f"  - Qdrant collections: {len(qdrant_collections)}")
        logger.info(f"  - Database records: {len(db_collections)}")
        logger.info(f"  - Missing in DB: {len(missing_in_db)}")
        logger.info(f"  - Extra in DB: {len(extra_in_db)}")

        if missing_in_db:
            logger.warning(f"⚠️  Collections missing from database: {missing_in_db}")

        if extra_in_db:
            logger.warning(f"⚠️  Extra database records: {extra_in_db}")

        if not missing_in_db and not extra_in_db:
            logger.info("✅ All collections are properly synchronized")
            return True
        else:
            logger.warning("⚠️  Collections are not fully synchronized")
            return False

        client.close()

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate existing Qdrant collections to database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate that all collections are properly migrated",
    )

    args = parser.parse_args()

    if args.validate:
        success = validate_migrated_collections()
        sys.exit(0 if success else 1)
    else:
        success = migrate_existing_collections(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
