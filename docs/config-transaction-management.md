# Configuration Transaction Management System

## Overview

The Configuration Transaction Management System provides comprehensive transactional editing capabilities for CiCLONE's pipeline configuration hierarchy. This sophisticated system enables safe, atomic editing of pipelines, stages, and operations with complete save/discard workflow management and intelligent dirty state tracking.

## System Architecture

### Core Components

```
ConfigTransactionManager
├── TransactionState (working memory)
├── ChangeRecord (audit trail)
├── Dirty State Tracking (hierarchical)
└── Context-Aware Prompting
```

### Key Classes and Enums

#### TransactionState
```python
@dataclass
class TransactionState:
    original_configs: List[Dict[str, Any]]  # From disk (immutable)
    working_configs: List[Dict[str, Any]]   # In-memory changes
    change_records: List[ChangeRecord]      # Audit trail
    deleted_pipeline_names: Set[str]        # Soft deletion tracking
    dirty_entities: Set[str] = field(default_factory=set)  # Hierarchical paths
    context_session_changes: Set[str] = field(default_factory=set)  # Current session
```

#### Entity Hierarchy
- **Pipeline Level**: `"pipeline:0"`
- **Stage Level**: `"pipeline:0:stage:1"`  
- **Operation Level**: `"pipeline:0:stage:1:operation:2"`

## Core Features

### 1. Memory-Only Transaction Model

**Design Principle**: All configuration changes remain in working memory until explicitly committed to disk via the main Save button.

**Benefits**:
- Safe experimentation without accidental persistence
- Atomic saves - either all changes succeed or none do
- Consistent "Save" semantics throughout the application
- Ability to discard entire editing sessions

**Implementation**:
```python
def _record_change(self, entity_path: str, change_type: ChangeType, 
                  field_name: str = None, old_value=None, new_value=None):
    """Records changes in memory only, never touches disk until save."""
    # Add to dirty entities for visual indicators
    self._transaction_state.dirty_entities.add(entity_path)
    
    # Track in current session for smart prompting
    self._transaction_state.context_session_changes.add(entity_path)
    
    # Check for revert-to-original and clean if needed
    if self._is_reverted_to_original(entity_path):
        self._clean_dirty_state(entity_path)
```

### 2. Hierarchical Dirty State Management

**Visual Indicators**: Real-time asterisk (*) indicators show modified entities at every level:
- `Pipeline Name *` - Pipeline has changes
- `Stage Name *` - Stage has changes  
- `1. operation_type *` - Operation has changes

**Enhanced Hierarchical Cleanup**: The `_clean_parent_dirty_states` method automatically removes parent dirty indicators when all children revert to original state:

```python
def _clean_parent_dirty_states(self, entity_path: str):
    """Clean parent entities' dirty states if they have no dirty children."""
    parts = entity_path.split(':')
    
    # Check pipeline level
    if len(parts) >= 2:  # pipeline:0
        pipeline_path = f"pipeline:{parts[1]}"
        pipeline_has_dirty_children = any(
            path.startswith(pipeline_path + ":") 
            for path in self._transaction_state.dirty_entities
        )
        if not pipeline_has_dirty_children:
            self._transaction_state.dirty_entities.discard(pipeline_path)
    
    # Check stage level  
    if len(parts) >= 4:  # pipeline:0:stage:1
        stage_path = f"pipeline:{parts[1]}:stage:{parts[3]}"
        stage_has_dirty_children = any(
            path.startswith(stage_path + ":") 
            for path in self._transaction_state.dirty_entities
        )
        if not stage_has_dirty_children:
            self._transaction_state.dirty_entities.discard(stage_path)
```

### 3. Intelligent Context Switching

**Smart Prompting System**: Only prompts users about unsaved changes when:
1. Actually switching to a different context (pipeline/stage/operation)
2. NEW modifications have been made in the current editing session
3. The target context differs from the current context

**Session Tracking**: The system maintains `context_session_changes` to track what was modified in the current editing session, eliminating unnecessary prompts when navigating back to previously-modified elements.

```python
def _should_prompt_for_context_change(self, new_context: Dict[str, int]) -> bool:
    """Determine if we should prompt user about context change."""
    if not self.has_changes_in_current_context_session():
        return False
        
    # Check if we're actually changing context
    current = self._current_context
    return (new_context['pipeline_index'] != current['pipeline_index'] or
            new_context['stage_index'] != current['stage_index'] or  
            new_context['operation_index'] != current['operation_index'])
```

### 4. Revert-to-Original Detection

**Automatic Cleanup**: When users change values back to their original state, the dirty indicators automatically disappear:

```python
def _is_reverted_to_original(self, entity_path: str) -> bool:
    """Check if entity has been reverted to its original state."""
    try:
        current_value = self._get_entity_value(entity_path)
        original_value = self._get_original_entity_value(entity_path)
        
        if isinstance(current_value, dict) and isinstance(original_value, dict):
            return self._deep_dict_equal(current_value, original_value)
        return current_value == original_value
        
    except Exception:
        return False
```

### 5. Context-Specific Rollback Methods

The system provides granular rollback capabilities at every hierarchical level:

```python
def rollback_pipeline(self, pipeline_index: int) -> bool:
    """Rollback all changes to a specific pipeline."""
    
def rollback_stage(self, pipeline_index: int, stage_index: int) -> bool:
    """Rollback all changes to a specific stage."""
    
def rollback_operation(self, pipeline_index: int, stage_index: int, operation_index: int) -> bool:
    """Rollback all changes to a specific operation."""
```

## Integration with UI Components

### ConfigDialogController

**Dialog Text Improvements**: Clear "Keep Changes" vs "Discard Changes" prompts:

```python
result = self.dialog_service.show_question_with_cancel(
    "Unsaved Changes",
    message,
    "Keep Changes", "Discard Changes", "Cancel"
)
```

**Context Management**:
- Tracks current pipeline/stage/operation indices
- Manages context transitions with smart prompting
- Coordinates rollback operations across the hierarchy

### PipelineConfigDialog

**Visual Indicators**: Real-time UI updates showing dirty state:

```python
def _update_pipeline_list(self, pipelines):
    """Update pipeline list with dirty indicators."""
    for i, pipeline in enumerate(pipelines):
        display_name = metadata.get('display_name', pipeline.get('name', 'Unknown'))
        
        # Add dirty indicator
        if self.controller.transaction_manager.is_pipeline_dirty(i):
            display_name += " *"
```

**Window Title Updates**: Shows overall unsaved changes status:
```python
if has_changes:
    self.setWindowTitle(f"{base_title} * (unsaved changes)")
else:
    self.setWindowTitle(base_title)
```

## Usage Patterns

### Basic Editing Workflow

1. **Load Configuration**: Transaction manager loads original configs from disk
2. **Edit in Memory**: All changes stored in `working_configs`, original remains untouched
3. **Visual Feedback**: Dirty indicators (*) appear instantly for modified entities
4. **Context Switching**: Smart prompts only when necessary
5. **Save or Discard**: Atomic operation - either all changes persist or none do

### Hierarchical State Management

```
Pipeline A *              # Has dirty children
├── Stage 1 *             # Modified stage
│   ├── Operation 1       # Clean
│   └── Operation 2 *     # Modified operation
├── Stage 2               # Clean (no dirty children)
│   ├── Operation 1       # Clean
│   └── Operation 2       # Clean
└── Stage 3 *             # Modified stage properties
    └── Operation 1       # Clean
```

When Operation 2 in Stage 1 reverts to original:
- Operation 2 indicator disappears
- Stage 1 remains dirty (still has stage-level changes)
- Pipeline A remains dirty (still has dirty children)

When Stage 1 reverts completely:
- Stage 1 indicator disappears  
- Pipeline A indicator disappears automatically (no dirty children)

## Error Handling and Edge Cases

### Concurrent Modification Protection
- Original configs remain immutable throughout transaction lifecycle
- Working configs are deep-copied to prevent reference issues
- Change detection uses deep comparison for complex objects

### Memory Management
- Dirty entities stored as Set[str] for O(1) lookup performance
- Context session tracking reset on successful context changes
- Change records maintain audit trail without excessive memory usage

### Validation and Consistency
- Entity path validation ensures proper hierarchy formatting
- Deep equality checking handles nested dictionary structures
- Graceful degradation when entity paths become invalid

## Performance Considerations

### Efficient Dirty State Tracking
- Set-based storage for O(1) dirty state lookups
- Hierarchical path prefixes enable efficient parent-child queries
- Context session changes tracked separately to minimize prompt overhead

### UI Update Optimization
- Dirty indicators updated only when state actually changes
- List refreshes batched to prevent excessive UI redraws
- Signal blocking during programmatic updates prevents cascade events

## Testing Strategy

### Unit Test Coverage
- Hierarchical cleanup scenarios with complex parent-child relationships
- Revert-to-original detection across different data types
- Context switching with various session change combinations
- Edge cases like empty configs, malformed paths, concurrent modifications

### Integration Testing
- Full save/discard workflows through UI components
- Visual indicator accuracy across all hierarchy levels
- Memory usage patterns during extended editing sessions
- Error recovery from disk I/O failures during save operations

## Best Practices

### For Developers
1. **Always use entity paths**: Consistent `"pipeline:0:stage:1:operation:2"` format
2. **Leverage dirty state checking**: Use `is_*_dirty()` methods for UI decisions
3. **Respect transaction boundaries**: Never bypass the transaction manager for config changes
4. **Test hierarchical scenarios**: Ensure parent-child state management works correctly

### For Users
1. **Visual feedback**: Trust the asterisk (*) indicators for change tracking
2. **Safe experimentation**: All changes remain in memory until explicit Save
3. **Context navigation**: Smart prompts only appear when necessary
4. **Atomic operations**: Save commits all changes, Discard reverts everything

## Future Enhancements

### Potential Improvements
- **Undo/Redo Stack**: Multi-level undo capability beyond single-transaction rollback
- **Change Diff Visualization**: Show exactly what changed between original and current state
- **Auto-save Draft**: Periodic automatic draft saves to prevent data loss
- **Collaborative Editing**: Multi-user change tracking and conflict resolution
- **Performance Monitoring**: Metrics for transaction size, memory usage, and operation timing

### Migration Considerations
- Current system provides solid foundation for enhanced versioning
- Entity path format is extensible for additional hierarchy levels
- Change record structure supports rich metadata for advanced features