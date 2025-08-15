"""
Configuration transaction management system for pipeline configuration editing.

This module provides comprehensive transactional editing capabilities for the entire 
configuration hierarchy: pipelines, stages, and operations, with complete save/discard
workflow management.
"""

import copy
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime


class ChangeType(Enum):
    """Types of changes that can occur in the configuration."""
    NONE = auto()
    ADDED = auto()
    MODIFIED = auto()
    DELETED = auto()
    REORDERED = auto()


class EntityLevel(Enum):
    """Hierarchy levels in the configuration."""
    PIPELINE = auto()
    STAGE = auto()
    OPERATION = auto()


@dataclass
class ChangeRecord:
    """Record of a single change in the configuration."""
    entity_level: EntityLevel
    change_type: ChangeType
    entity_path: str  # e.g., "pipeline:0", "pipeline:0:stage:1", "pipeline:0:stage:1:operation:2"
    field_name: Optional[str] = None
    old_value: Any = None
    new_value: Any = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TransactionState:
    """Represents the complete state of a configuration transaction."""
    original_configs: List[Dict[str, Any]]  # From disk (never changes)
    working_configs: List[Dict[str, Any]]   # All in-memory changes
    change_records: List[ChangeRecord] = field(default_factory=list)
    deleted_pipeline_names: Set[str] = field(default_factory=set)
    
    # NEW: Track dirty state for UI indicators
    dirty_entities: Set[str] = field(default_factory=set)  # entity paths that are dirty
    
    # REMOVE: No longer needed - no intermediate commits
    # is_committed: bool = False
    # is_rolled_back: bool = False


class ConfigTransactionManager:
    """
    Manages all configuration transactions with comprehensive save/discard workflow.
    Provides a single source of truth for all configuration state and changes.
    """
    
    def __init__(self):
        """Initialize the unified transaction manager."""
        self._transaction_state: Optional[TransactionState] = None
        self._change_listeners: List[Callable[[ChangeRecord], None]] = []
        self._dirty_check_enabled: bool = True
        self._initialization_mode: bool = False
        
        # Current context tracking for intelligent prompting
        self._current_context = {
            'pipeline_index': -1,
            'stage_index': -1,
            'operation_index': -1
        }
        
        # Track changes made in current context (reset when context changes)
        self._context_change_count = 0
        
        # Snapshot management for fine-grained change detection
        self._snapshots: Dict[str, Any] = {}
    
    # ==================== Transaction Lifecycle ====================
    
    def begin_transaction(self, original_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Start a new configuration transaction.
        
        Args:
            original_configs: The original list of pipeline configurations
            
        Returns:
            List of pipeline configurations in working copy
        """
        # Clear any existing transaction state
        self._transaction_state = TransactionState(
            original_configs=copy.deepcopy(original_configs),
            working_configs=copy.deepcopy(original_configs)
        )
        
        self._initialization_mode = True
        self._take_initial_snapshots()
        
        return self.get_working_configs()
    
    def commit_transaction(self) -> Tuple[List[Dict[str, Any]], Set[str]]:
        """
        Commit all changes permanently.
        
        Returns:
            Tuple of (committed configurations, deleted pipeline names)
        """
        if not self._transaction_state:
            raise RuntimeError("No active transaction to commit")
        
        # Create final copies for return
        committed_configs = copy.deepcopy(self._transaction_state.working_configs)
        deleted_names = self._transaction_state.deleted_pipeline_names.copy()
        
        # Clear dirty entities after commit
        self._transaction_state.dirty_entities.clear()
        self._transaction_state.change_records.clear()
        
        return committed_configs, deleted_names
    
    def rollback_transaction(self) -> List[Dict[str, Any]]:
        """
        Revert all changes to original state.
        
        Returns:
            The original configuration list
        """
        if not self._transaction_state:
            raise RuntimeError("No active transaction to rollback")
        
        # Store original configs before clearing transaction state
        original_configs = copy.deepcopy(self._transaction_state.original_configs)
        
        # Clear transaction state completely to allow new transaction
        self._transaction_state = None
        self._snapshots.clear()
        
        return original_configs
    
    
    
    def end_initialization(self) -> None:
        """Mark initialization as complete and enable change tracking."""
        self._initialization_mode = False
        if self._transaction_state:
            # Reset original state to match working state after initialization
            self._transaction_state.original_configs = copy.deepcopy(
                self._transaction_state.working_configs
            )
            self._transaction_state.change_records.clear()
            self._transaction_state.deleted_pipeline_names.clear()
            self._take_initial_snapshots()
    
    # ==================== Change Detection ====================
    
    def has_changes(self) -> bool:
        """
        Check if there are any uncommitted changes.
        
        Returns:
            True if there are uncommitted changes
        """
        if self._initialization_mode or not self._dirty_check_enabled:
            return False
        
        if not self._transaction_state:
            return False
        
        # Check for any recorded changes
        if self._transaction_state.change_records:
            return True
        
        # Check for deleted pipelines
        if self._transaction_state.deleted_pipeline_names:
            return True
        
        # Deep comparison as fallback
        return self._transaction_state.working_configs != self._transaction_state.original_configs
    
    def has_changes_at_level(self, level: EntityLevel, indices: Dict[str, int]) -> bool:
        """
        Check if there are changes at a specific level and location.
        
        Args:
            level: The entity level to check
            indices: Dictionary with 'pipeline', 'stage', 'operation' indices
            
        Returns:
            True if there are changes at the specified level
        """
        if not self.has_changes():
            return False
        
        path_prefix = self._build_entity_path(level, indices)
        
        for record in self._transaction_state.change_records:
            if record.entity_path.startswith(path_prefix):
                return True
        
        return False
    
    def get_change_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all pending changes.
        
        Returns:
            Dictionary with change counts by type and level
        """
        if not self._transaction_state:
            return {}
        
        summary = {
            'total_changes': len(self._transaction_state.change_records),
            'deleted_pipelines': len(self._transaction_state.deleted_pipeline_names),
            'by_level': {
                EntityLevel.PIPELINE: 0,
                EntityLevel.STAGE: 0,
                EntityLevel.OPERATION: 0
            },
            'by_type': {
                ChangeType.ADDED: 0,
                ChangeType.MODIFIED: 0,
                ChangeType.DELETED: 0,
                ChangeType.REORDERED: 0
            }
        }
        
        for record in self._transaction_state.change_records:
            summary['by_level'][record.entity_level] += 1
            summary['by_type'][record.change_type] += 1
        
        return summary
    
    # ==================== Dirty State Tracking ====================
    
    def is_entity_dirty(self, entity_path: str) -> bool:
        """Check if a specific entity path has unsaved changes.
        
        Args:
            entity_path: Entity path like "pipeline:0" or "pipeline:0:stage:1"
            
        Returns:
            True if entity has unsaved changes
        """
        if not self._transaction_state:
            return False
        return entity_path in self._transaction_state.dirty_entities

    def get_dirty_entities(self) -> Set[str]:
        """Get all dirty entity paths.
        
        Returns:
            Set of entity paths that have unsaved changes
        """
        if not self._transaction_state:
            return set()
        return self._transaction_state.dirty_entities.copy()

    def is_pipeline_dirty(self, pipeline_index: int) -> bool:
        """Check if a pipeline or any of its contents are dirty.
        
        Args:
            pipeline_index: Index of pipeline to check
            
        Returns:
            True if pipeline has any unsaved changes
        """
        if not self._transaction_state:
            return False
        
        pipeline_path = f"pipeline:{pipeline_index}"
        
        # Check if any dirty entity starts with this pipeline path
        for dirty_path in self._transaction_state.dirty_entities:
            if dirty_path.startswith(pipeline_path):
                return True
        
        return False

    def is_stage_dirty(self, pipeline_index: int, stage_index: int) -> bool:
        """Check if a stage or any of its operations are dirty.
        
        Args:
            pipeline_index: Index of pipeline
            stage_index: Index of stage
            
        Returns:
            True if stage has any unsaved changes
        """
        if not self._transaction_state:
            return False
        
        stage_path = f"pipeline:{pipeline_index}:stage:{stage_index}"
        
        # Check if any dirty entity starts with this stage path
        for dirty_path in self._transaction_state.dirty_entities:
            if dirty_path.startswith(stage_path):
                return True
        
        return False

    def is_operation_dirty(self, pipeline_index: int, stage_index: int, operation_index: int) -> bool:
        """Check if an operation is dirty.
        
        Args:
            pipeline_index: Index of pipeline
            stage_index: Index of stage  
            operation_index: Index of operation
            
        Returns:
            True if operation has unsaved changes
        """
        if not self._transaction_state:
            return False
        
        operation_path = f"pipeline:{pipeline_index}:stage:{stage_index}:operation:{operation_index}"
        return operation_path in self._transaction_state.dirty_entities

    def get_dirty_display_names(self) -> Dict[str, str]:
        """Get display names for all dirty entities for UI indicators.
        
        Returns:
            Dict mapping entity paths to display names with * indicator
        """
        if not self._transaction_state:
            return {}
        
        display_names = {}
        
        for dirty_path in self._transaction_state.dirty_entities:
            entity = self._get_entity_by_path(dirty_path)
            if entity:
                # Extract display name based on entity type
                if 'pipeline:' in dirty_path and ':stage:' not in dirty_path:
                    # Pipeline level
                    name = entity.get('name', 'Unnamed Pipeline')
                    display_names[dirty_path] = f"{name} *"
                elif ':stage:' in dirty_path and ':operation:' not in dirty_path:
                    # Stage level  
                    name = entity.get('name', 'Unnamed Stage')
                    display_names[dirty_path] = f"{name} *"
                elif ':operation:' in dirty_path:
                    # Operation level
                    name = entity.get('type', 'to_be_defined')
                    display_names[dirty_path] = f"{name} *"
        
        return display_names
    
    def has_changes_in_current_context_session(self) -> bool:
        """Check if changes were made during the current context session.
        
        Returns:
            True if changes were made since entering current context
        """
        return self._context_change_count > 0
    
    # ==================== Pipeline Operations ====================
    
    def get_working_configs(self) -> List[Dict[str, Any]]:
        """Get the current working pipeline configurations."""
        if not self._transaction_state:
            return []
        return self._transaction_state.working_configs
    
    def add_pipeline(self, pipeline_data: Dict[str, Any]) -> int:
        """
        Add a new pipeline to the working copy.
        
        Args:
            pipeline_data: Pipeline data to add
            
        Returns:
            Index of the newly added pipeline
        """
        if not self._transaction_state:
            raise RuntimeError("No active transaction")
        
        # Create a copy and mark as new
        new_pipeline = copy.deepcopy(pipeline_data)
        
        # Add metadata to mark this as a new pipeline
        if '_metadata' not in new_pipeline:
            new_pipeline['_metadata'] = {}
        new_pipeline['_metadata']['is_new'] = True
        
        # Set stage count for proper UI display
        stages = new_pipeline.get('stages', [])
        stage_count = len(stages)
        new_pipeline['_metadata']['stage_count'] = stage_count
        
        # Set display name from pipeline name
        pipeline_name = new_pipeline.get('name', 'Unnamed Pipeline')
        new_pipeline['_metadata']['display_name'] = pipeline_name
        new_pipeline['_metadata']['config_name'] = pipeline_name  # Use pipeline name as config name for new pipelines
        
        working = self._transaction_state.working_configs
        working.append(new_pipeline)
        new_index = len(working) - 1
        
        # Record the change
        self._record_change(
            EntityLevel.PIPELINE,
            ChangeType.ADDED,
            {'pipeline': new_index},
            new_value=new_pipeline
        )
        
        return new_index
    
    def update_pipeline(self, index: int, field: str, value: Any) -> bool:
        """
        Update a pipeline field.
        
        Args:
            index: Pipeline index
            field: Field name to update
            value: New value
            
        Returns:
            True if update was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= index < len(working):
            old_value = working[index].get(field)
            
            if old_value != value:
                working[index][field] = value
                
                # Record the change
                self._record_change(
                    EntityLevel.PIPELINE,
                    ChangeType.MODIFIED,
                    {'pipeline': index},
                    field_name=field,
                    old_value=old_value,
                    new_value=value
                )
            
            return True
        return False
    
    def delete_pipeline(self, index: int) -> bool:
        """
        Delete a pipeline from the working copy.
        
        Args:
            index: Pipeline index to delete
            
        Returns:
            True if deletion was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= index < len(working):
            pipeline = working.pop(index)
            pipeline_name = pipeline.get('name', '')
            
            # Track deletion if it's an original pipeline
            if pipeline in self._transaction_state.original_configs:
                if pipeline_name:
                    self._transaction_state.deleted_pipeline_names.add(pipeline_name)
            
            # Record the change
            self._record_change(
                EntityLevel.PIPELINE,
                ChangeType.DELETED,
                {'pipeline': index},
                old_value=pipeline
            )
            
            return True
        return False
    
    # ==================== Stage Operations ====================
    
    def add_stage(self, pipeline_index: int, stage_data: Dict[str, Any]) -> int:
        """
        Add a new stage to a pipeline.
        
        Args:
            pipeline_index: Index of pipeline
            stage_data: Stage data to add
            
        Returns:
            Index of the newly added stage
        """
        if not self._transaction_state:
            return -1
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].setdefault('stages', [])
            stages.append(copy.deepcopy(stage_data))
            new_index = len(stages) - 1
            
            # Record the change
            self._record_change(
                EntityLevel.STAGE,
                ChangeType.ADDED,
                {'pipeline': pipeline_index, 'stage': new_index},
                new_value=stage_data
            )
            
            # Update stage count metadata if present
            self._update_pipeline_stage_count(pipeline_index)
            
            return new_index
        return -1
    
    def update_stage(self, pipeline_index: int, stage_index: int, 
                     field: str, value: Any) -> bool:
        """
        Update a stage field.
        
        Args:
            pipeline_index: Pipeline index
            stage_index: Stage index
            field: Field name to update
            value: New value
            
        Returns:
            True if update was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            if 0 <= stage_index < len(stages):
                old_value = stages[stage_index].get(field)
                
                if old_value != value:
                    stages[stage_index][field] = value
                    
                    # Record the change
                    self._record_change(
                        EntityLevel.STAGE,
                        ChangeType.MODIFIED,
                        {'pipeline': pipeline_index, 'stage': stage_index},
                        field_name=field,
                        old_value=old_value,
                        new_value=value
                    )
                
                return True
        return False
    
    def delete_stage(self, pipeline_index: int, stage_index: int) -> bool:
        """
        Delete a stage from a pipeline.
        
        Args:
            pipeline_index: Pipeline index
            stage_index: Stage index to delete
            
        Returns:
            True if deletion was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            if 0 <= stage_index < len(stages):
                stage = stages.pop(stage_index)
                
                # Record the change
                self._record_change(
                    EntityLevel.STAGE,
                    ChangeType.DELETED,
                    {'pipeline': pipeline_index, 'stage': stage_index},
                    old_value=stage
                )
                
                # Update stage count metadata if present
                self._update_pipeline_stage_count(pipeline_index)
                
                return True
        return False
    
    def reorder_stage(self, pipeline_index: int, from_index: int, to_index: int) -> bool:
        """
        Reorder a stage within a pipeline.
        
        Args:
            pipeline_index: Pipeline index
            from_index: Current stage index
            to_index: Target stage index
            
        Returns:
            True if reorder was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            if (0 <= from_index < len(stages) and 
                0 <= to_index < len(stages) and 
                from_index != to_index):
                
                stage = stages.pop(from_index)
                stages.insert(to_index, stage)
                
                # Record the change
                self._record_change(
                    EntityLevel.STAGE,
                    ChangeType.REORDERED,
                    {'pipeline': pipeline_index, 'stage': from_index},
                    old_value=from_index,
                    new_value=to_index
                )
                
                return True
        return False
    
    # ==================== Operation Operations ====================
    
    def add_operation(self, pipeline_index: int, stage_index: int, 
                      operation_data: Dict[str, Any]) -> int:
        """
        Add a new operation to a stage.
        
        Args:
            pipeline_index: Pipeline index
            stage_index: Stage index
            operation_data: Operation data to add
            
        Returns:
            Index of the newly added operation
        """
        if not self._transaction_state:
            return -1
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            if 0 <= stage_index < len(stages):
                operations = stages[stage_index].setdefault('operations', [])
                
                # Ensure config format
                config_op = self._ensure_config_format(operation_data)
                operations.append(config_op)
                new_index = len(operations) - 1
                
                # Record the change
                self._record_change(
                    EntityLevel.OPERATION,
                    ChangeType.ADDED,
                    {'pipeline': pipeline_index, 'stage': stage_index, 
                     'operation': new_index},
                    new_value=config_op
                )
                
                return new_index
        return -1
    
    def update_operation(self, pipeline_index: int, stage_index: int, 
                        operation_index: int, operation_data: Dict[str, Any]) -> bool:
        """
        Update an operation.
        
        Args:
            pipeline_index: Pipeline index
            stage_index: Stage index
            operation_index: Operation index
            operation_data: New operation data
            
        Returns:
            True if update was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            
            if 0 <= stage_index < len(stages):
                operations = stages[stage_index].get('operations', [])
                
                if 0 <= operation_index < len(operations):
                    old_value = operations[operation_index]
                    config_op = self._ensure_config_format(operation_data)
                    
                    if old_value != config_op:
                        # Update the operation
                        operations[operation_index] = config_op
                        
                        # Always use centralized _record_change method
                        # This will handle revert detection automatically
                        self._record_change(
                            EntityLevel.OPERATION,
                            ChangeType.MODIFIED,
                            {'pipeline': pipeline_index, 'stage': stage_index,
                             'operation': operation_index},
                            old_value=old_value,
                            new_value=config_op
                        )
                    
                    return True
            
        return False
    
    def delete_operation(self, pipeline_index: int, stage_index: int, 
                        operation_index: int) -> bool:
        """
        Delete an operation from a stage.
        
        Args:
            pipeline_index: Pipeline index
            stage_index: Stage index
            operation_index: Operation index to delete
            
        Returns:
            True if deletion was successful
        """
        if not self._transaction_state:
            return False
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            stages = working[pipeline_index].get('stages', [])
            if 0 <= stage_index < len(stages):
                operations = stages[stage_index].get('operations', [])
                if 0 <= operation_index < len(operations):
                    operation = operations.pop(operation_index)
                    
                    # Record the change
                    self._record_change(
                        EntityLevel.OPERATION,
                        ChangeType.DELETED,
                        {'pipeline': pipeline_index, 'stage': stage_index,
                         'operation': operation_index},
                        old_value=operation
                    )
                    
                    return True
        return False
    
    # ==================== Context Management ====================
    
    def set_current_context(self, pipeline_index: int = -1, 
                           stage_index: int = -1, 
                           operation_index: int = -1):
        """
        Set the current editing context for intelligent prompting.
        
        Args:
            pipeline_index: Current pipeline index
            stage_index: Current stage index
            operation_index: Current operation index
        """
        # Reset context change counter when context changes
        self._context_change_count = 0
        
        self._current_context = {
            'pipeline_index': pipeline_index,
            'stage_index': stage_index,
            'operation_index': operation_index
        }
    
    def rollback_pipeline_context(self, pipeline_index: int) -> bool:
        """Rollback all changes to a specific pipeline without affecting others.
        
        Args:
            pipeline_index: Index of pipeline to rollback
            
        Returns:
            True if rollback was successful
        """
        if not self._transaction_state or pipeline_index < 0:
            return False
        
        # Find original pipeline
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        
        # Restore pipeline in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_configs[pipeline_index] = copy.deepcopy(original_pipeline)
        
        # Remove all change records and dirty markers for this pipeline
        pipeline_path = f"pipeline:{pipeline_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == pipeline_path or record.entity_path.startswith(pipeline_path + ":")
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        # Remove dirty markers for this pipeline and all its children
        dirty_to_remove = [
            path for path in self._transaction_state.dirty_entities
            if path == pipeline_path or path.startswith(pipeline_path + ":")
        ]
        
        for path in dirty_to_remove:
            self._transaction_state.dirty_entities.remove(path)
        
        return True

    def rollback_stage_context(self, pipeline_index: int, stage_index: int) -> bool:
        """Rollback all changes to a specific stage without affecting others.
        
        Args:
            pipeline_index: Index of pipeline
            stage_index: Index of stage
            
        Returns:
            True if rollback was successful
        """
        if not self._transaction_state or pipeline_index < 0 or stage_index < 0:
            return False
        
        # Find original stage
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        original_stages = original_pipeline.get('stages', [])
        
        if stage_index >= len(original_stages):
            return False
        
        original_stage = original_stages[stage_index]
        
        # Restore stage in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_pipeline = working_configs[pipeline_index]
            working_stages = working_pipeline.get('stages', [])
            
            if stage_index < len(working_stages):
                working_stages[stage_index] = copy.deepcopy(original_stage)
        
        # Remove all change records and dirty markers for this stage
        stage_path = f"pipeline:{pipeline_index}:stage:{stage_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == stage_path or record.entity_path.startswith(stage_path + ":")
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        # Remove dirty markers for this stage and all its children
        dirty_to_remove = [
            path for path in self._transaction_state.dirty_entities
            if path == stage_path or path.startswith(stage_path + ":")
        ]
        
        for path in dirty_to_remove:
            self._transaction_state.dirty_entities.remove(path)
        
        return True

    def rollback_operation_context(self, pipeline_index: int, stage_index: int, operation_index: int) -> bool:
        """Rollback all changes to a specific operation.
        
        Args:
            pipeline_index: Index of pipeline
            stage_index: Index of stage  
            operation_index: Index of operation
            
        Returns:
            True if rollback was successful
        """
        if (not self._transaction_state or pipeline_index < 0 or 
            stage_index < 0 or operation_index < 0):
            return False
        
        # Find original operation
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        original_stages = original_pipeline.get('stages', [])
        
        if stage_index >= len(original_stages):
            return False
        
        original_stage = original_stages[stage_index]
        original_operations = original_stage.get('operations', [])
        
        if operation_index >= len(original_operations):
            return False
        
        original_operation = original_operations[operation_index]
        
        # Restore operation in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_pipeline = working_configs[pipeline_index]
            working_stages = working_pipeline.get('stages', [])
            
            if stage_index < len(working_stages):
                working_stage = working_stages[stage_index]
                working_operations = working_stage.get('operations', [])
                
                if operation_index < len(working_operations):
                    working_operations[operation_index] = copy.deepcopy(original_operation)
        
        # Remove all change records and dirty markers for this operation
        operation_path = f"pipeline:{pipeline_index}:stage:{stage_index}:operation:{operation_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == operation_path
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        # Remove dirty marker for this operation
        self._transaction_state.dirty_entities.discard(operation_path)
        
        return True
    
    
    def check_context_switch(self, new_pipeline: int = None, 
                           new_stage: int = None, 
                           new_operation: int = None) -> bool:
        """
        Check if switching context would lose unsaved changes made in current context session.
        
        Args:
            new_pipeline: New pipeline index
            new_stage: New stage index
            new_operation: New operation index
            
        Returns:
            True if there are unsaved changes made in current context session
        """
        # Only prompt if we made changes during the current context session
        if not self.has_changes_in_current_context_session():
            return False
        
        # For pipeline switching, prompt if any changes were made in current session
        if new_pipeline is not None and new_pipeline != self._current_context['pipeline_index']:
            return True
        
        # For stage switching within the same pipeline, prompt if changes in current session
        if (new_stage is not None and 
            new_stage != self._current_context['stage_index'] and
            self._current_context['stage_index'] >= 0):
            return True
        
        # For operation switching within the same stage, prompt if changes in current session  
        if (new_operation is not None and 
            new_operation != self._current_context['operation_index'] and
            self._current_context['operation_index'] >= 0):
            return True
        
        return False
    
    # ==================== Snapshot Management ====================
    
    
    
    # ==================== Change Listeners ====================
    
    def add_change_listener(self, listener: Callable[[ChangeRecord], None]) -> None:
        """Add a listener for change events."""
        self._change_listeners.append(listener)
    
    
    # ==================== Utility Methods ====================
    
    
    def get_pipeline(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a specific pipeline from working configs."""
        if not self._transaction_state:
            return None
        
        working = self._transaction_state.working_configs
        if 0 <= index < len(working):
            return working[index]
        return None
    
    def get_stage(self, pipeline_index: int, stage_index: int) -> Optional[Dict[str, Any]]:
        """Get a specific stage from a pipeline."""
        pipeline = self.get_pipeline(pipeline_index)
        if pipeline:
            stages = pipeline.get('stages', [])
            if 0 <= stage_index < len(stages):
                return stages[stage_index]
        return None
    
    def get_operation(self, pipeline_index: int, stage_index: int, 
                     operation_index: int) -> Optional[Dict[str, Any]]:
        """Get a specific operation from a stage."""
        stage = self.get_stage(pipeline_index, stage_index)
        if stage:
            operations = stage.get('operations', [])
            if 0 <= operation_index < len(operations):
                return operations[operation_index]
        return None
    
    # ==================== Private Methods ====================
    
    def _is_revert_to_original(self, entity_path: str, field_name: Optional[str], new_value: Any) -> bool:
        """Check if a change reverts an entity back to its original value."""
        if not self._transaction_state:
            return False
        
        # Get the original entity
        original_entity = self._get_original_entity_by_path(entity_path)
        if original_entity is None:
            return False
        
        # Compare with original value
        if field_name:
            # Field-level change
            original_field_value = original_entity.get(field_name)
            return original_field_value == new_value
        else:
            # Entity-level change  
            return original_entity == new_value
    
    def _clean_dirty_state_if_reverted(self, entity_path: str, field_name: Optional[str]):
        """Clean up dirty state if entity has been reverted to original."""
        if not self._transaction_state:
            return
        
        # Remove change records for this entity/field
        if field_name:
            # Remove records for this specific field
            records_to_remove = [
                record for record in self._transaction_state.change_records
                if record.entity_path == entity_path and record.field_name == field_name
            ]
        else:
            # Remove all records for this entity
            records_to_remove = [
                record for record in self._transaction_state.change_records
                if record.entity_path == entity_path
            ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        # Check if entity has any remaining changes
        has_remaining_changes = any(
            record.entity_path == entity_path
            for record in self._transaction_state.change_records
        )
        
        # If no remaining changes, remove from dirty entities
        if not has_remaining_changes:
            self._transaction_state.dirty_entities.discard(entity_path)
            
            # Clean parent entities if they no longer have dirty children
            self._clean_parent_dirty_states(entity_path)
    
    def _clean_parent_dirty_states(self, entity_path: str):
        """Clean parent entities' dirty states if they have no dirty children."""
        if not self._transaction_state:
            return
        
        parts = entity_path.split(':')
        
        # Work backwards through the hierarchy
        # For operation -> check stage and pipeline
        # For stage -> check pipeline
        
        if len(parts) == 6 and parts[4] == 'operation':
            # This is an operation, check its parent stage
            stage_path = ':'.join(parts[:4])  # pipeline:X:stage:Y
            
            # Check if stage has any dirty children (operations)
            has_dirty_operations = any(
                path.startswith(stage_path + ':operation:')
                for path in self._transaction_state.dirty_entities
            )
            
            # Check if stage itself has changes
            has_stage_changes = any(
                record.entity_path == stage_path
                for record in self._transaction_state.change_records
            )
            
            # If stage has no dirty operations and no own changes, clean it
            if not has_dirty_operations and not has_stage_changes:
                self._transaction_state.dirty_entities.discard(stage_path)
                
                # Now check the pipeline
                pipeline_path = ':'.join(parts[:2])  # pipeline:X
                self._clean_pipeline_if_no_dirty_children(pipeline_path)
                
        elif len(parts) == 4 and parts[2] == 'stage':
            # This is a stage, check its parent pipeline
            pipeline_path = ':'.join(parts[:2])  # pipeline:X
            self._clean_pipeline_if_no_dirty_children(pipeline_path)
    
    def _clean_pipeline_if_no_dirty_children(self, pipeline_path: str):
        """Clean pipeline dirty state if it has no dirty children."""
        if not self._transaction_state:
            return
            
        # Check if pipeline has any dirty children (stages or operations)
        has_dirty_children = any(
            path.startswith(pipeline_path + ':') and path != pipeline_path
            for path in self._transaction_state.dirty_entities
        )
        
        # Check if pipeline itself has changes
        has_pipeline_changes = any(
            record.entity_path == pipeline_path
            for record in self._transaction_state.change_records
        )
        
        # If pipeline has no dirty children and no own changes, clean it
        if not has_dirty_children and not has_pipeline_changes:
            self._transaction_state.dirty_entities.discard(pipeline_path)
    
    def _get_original_entity_by_path(self, entity_path: str) -> Optional[Any]:
        """Get an entity from the original configs by its path string."""
        if not self._transaction_state:
            return None
        
        parts = entity_path.split(':')
        
        if len(parts) < 2:
            return None
        
        # Parse pipeline index
        if parts[0] != 'pipeline':
            return None
        
        pipeline_index = int(parts[1])
        original_configs = self._transaction_state.original_configs
        
        if pipeline_index >= len(original_configs):
            return None
        
        pipeline = original_configs[pipeline_index]
        
        if len(parts) == 2:
            return pipeline
        
        # Parse stage index if present
        if len(parts) >= 4 and parts[2] == 'stage':
            stage_index = int(parts[3])
            stages = pipeline.get('stages', [])
            
            if stage_index >= len(stages):
                return None
            
            stage = stages[stage_index]
            
            if len(parts) == 4:
                return stage
            
            # Parse operation index if present
            if len(parts) == 6 and parts[4] == 'operation':
                operation_index = int(parts[5])
                operations = stage.get('operations', [])
                
                if operation_index >= len(operations):
                    return None
                    
                return operations[operation_index]
        
        return None
    
    def _record_change(self, entity_level: EntityLevel, change_type: ChangeType,
                      indices: Dict[str, int], field_name: Optional[str] = None,
                      old_value: Any = None, new_value: Any = None):
        """Record a change in the transaction."""
        if self._initialization_mode:
            return
        
        entity_path = self._build_entity_path(entity_level, indices)
        
        # Check if this change reverts to original value
        if self._is_revert_to_original(entity_path, field_name, new_value):
            # Remove from dirty entities if this change brings it back to original
            self._clean_dirty_state_if_reverted(entity_path, field_name)
            return
        
        record = ChangeRecord(
            entity_level=entity_level,
            change_type=change_type,
            entity_path=entity_path,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value
        )
        
        self._transaction_state.change_records.append(record)
        
        # NEW: Mark entity as dirty
        self._transaction_state.dirty_entities.add(entity_path)
        
        # Track that we made a change in current context
        self._context_change_count += 1
        
        # Notify listeners
        for listener in self._change_listeners:
            listener(record)
    
    def _build_entity_path(self, entity_level: EntityLevel, 
                          indices: Dict[str, int]) -> str:
        """Build an entity path string from indices."""
        path_parts = []
        
        if 'pipeline' in indices:
            path_parts.append(f"pipeline:{indices['pipeline']}")
        
        if entity_level in [EntityLevel.STAGE, EntityLevel.OPERATION] and 'stage' in indices:
            path_parts.append(f"stage:{indices['stage']}")
        
        if entity_level == EntityLevel.OPERATION and 'operation' in indices:
            path_parts.append(f"operation:{indices['operation']}")
        
        return ":".join(path_parts)
    
    def _get_entity_by_path(self, entity_path: str) -> Optional[Any]:
        """Get an entity by its path string."""
        if not self._transaction_state:
            return None
        
        parts = entity_path.split(':')
        
        if len(parts) < 2:
            return None
        
        # Parse pipeline index
        if parts[0] != 'pipeline':
            return None
        
        pipeline_index = int(parts[1])
        pipeline = self.get_pipeline(pipeline_index)
        
        if len(parts) == 2:
            return pipeline
        
        # Parse stage index if present
        if len(parts) >= 4 and parts[2] == 'stage':
            stage_index = int(parts[3])
            stage = self.get_stage(pipeline_index, stage_index)
            
            if len(parts) == 4:
                return stage
            
            # Parse operation index if present
            if len(parts) == 6 and parts[4] == 'operation':
                operation_index = int(parts[5])
                return self.get_operation(pipeline_index, stage_index, operation_index)
        
        return None
    
    def _ensure_config_format(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert operation data to config format if needed."""
        if 'type' in operation_data:
            return copy.deepcopy(operation_data)
        
        return {
            'type': operation_data.get('operation', 'to_be_defined'),
            'workdir': operation_data.get('workdir', ''),
            'files': operation_data.get('files', [])
        }
    
    def _take_initial_snapshots(self):
        """Take initial snapshots of all entities."""
        if not self._transaction_state:
            return
        
        self._snapshots.clear()
        
        for i, pipeline in enumerate(self._transaction_state.working_configs):
            pipeline_path = f"pipeline:{i}"
            self._snapshots[pipeline_path] = copy.deepcopy(pipeline)
            
            for j, stage in enumerate(pipeline.get('stages', [])):
                stage_path = f"{pipeline_path}:stage:{j}"
                self._snapshots[stage_path] = copy.deepcopy(stage)
                
                for k, operation in enumerate(stage.get('operations', [])):
                    operation_path = f"{stage_path}:operation:{k}"
                    self._snapshots[operation_path] = copy.deepcopy(operation)
    
    
    
    def _rollback_pipeline_changes(self, pipeline_index: int) -> bool:
        """Rollback all changes to a specific pipeline."""
        if not self._transaction_state or pipeline_index is None:
            return False
        
        # Find original pipeline
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        
        # Restore pipeline in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_configs[pipeline_index] = copy.deepcopy(original_pipeline)
        
        # Remove all change records for this pipeline
        pipeline_path = f"pipeline:{pipeline_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == pipeline_path or record.entity_path.startswith(pipeline_path + ":")
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        return True
    
    def _rollback_stage_changes(self, pipeline_index: int, stage_index: int) -> bool:
        """Rollback all changes to a specific stage."""
        if not self._transaction_state or pipeline_index is None or stage_index is None:
            return False
        
        # Find original stage
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        original_stages = original_pipeline.get('stages', [])
        
        if stage_index >= len(original_stages):
            return False
        
        original_stage = original_stages[stage_index]
        
        # Restore stage in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_pipeline = working_configs[pipeline_index]
            working_stages = working_pipeline.get('stages', [])
            
            if stage_index < len(working_stages):
                working_stages[stage_index] = copy.deepcopy(original_stage)
        
        # Remove all change records for this stage
        stage_path = f"pipeline:{pipeline_index}:stage:{stage_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == stage_path or record.entity_path.startswith(stage_path + ":")
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        return True
    
    def _rollback_operation_changes(self, pipeline_index: int, stage_index: int, 
                                   operation_index: int) -> bool:
        """Rollback all changes to a specific operation."""
        if (not self._transaction_state or pipeline_index is None or 
            stage_index is None or operation_index is None):
            return False
        
        # Find original operation
        original_configs = self._transaction_state.original_configs
        if pipeline_index >= len(original_configs):
            return False
        
        original_pipeline = original_configs[pipeline_index]
        original_stages = original_pipeline.get('stages', [])
        
        if stage_index >= len(original_stages):
            return False
        
        original_stage = original_stages[stage_index]
        original_operations = original_stage.get('operations', [])
        
        if operation_index >= len(original_operations):
            return False
        
        original_operation = original_operations[operation_index]
        
        # Restore operation in working configs
        working_configs = self._transaction_state.working_configs
        if pipeline_index < len(working_configs):
            working_pipeline = working_configs[pipeline_index]
            working_stages = working_pipeline.get('stages', [])
            
            if stage_index < len(working_stages):
                working_stage = working_stages[stage_index]
                working_operations = working_stage.get('operations', [])
                
                if operation_index < len(working_operations):
                    working_operations[operation_index] = copy.deepcopy(original_operation)
        
        # Remove all change records for this operation
        operation_path = f"pipeline:{pipeline_index}:stage:{stage_index}:operation:{operation_index}"
        records_to_remove = [
            record for record in self._transaction_state.change_records
            if record.entity_path == operation_path
        ]
        
        for record in records_to_remove:
            self._transaction_state.change_records.remove(record)
        
        return True
    
    def _update_pipeline_stage_count(self, pipeline_index: int):
        """Update the stage count metadata for a pipeline."""
        if not self._transaction_state:
            return
        
        working = self._transaction_state.working_configs
        if 0 <= pipeline_index < len(working):
            pipeline = working[pipeline_index]
            stages = pipeline.get('stages', [])
            stage_count = len(stages)
            
            # Update metadata if it exists
            if '_metadata' in pipeline:
                pipeline['_metadata']['stage_count'] = stage_count