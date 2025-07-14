"""
Unit tests for ElectrodeViewDelegate.

Tests the view delegate that was created to remove UI dependencies from the 
ElectrodeModel while maintaining the same functionality.
"""

import unittest
import sys
from unittest.mock import Mock, patch

# Mock PyQt6 components for testing in environments without GUI
class MockQTreeWidgetItem:
    def __init__(self, parent=None):
        self.parent = parent
        self._texts = {}
        self._alignments = {}
        self.children = []
        if parent:
            parent.children.append(self)
    
    def setText(self, column, text):
        self._texts[column] = text
    
    def text(self, column):
        return self._texts.get(column, "")
    
    def setTextAlignment(self, column, alignment):
        self._alignments[column] = alignment
    
    def childCount(self):
        return len(self.children)
    
    def child(self, index):
        return self.children[index] if 0 <= index < len(self.children) else None

class MockQt:
    class AlignmentFlag:
        AlignCenter = 'AlignCenter'

# Mock the PyQt6 modules
sys.modules['PyQt6'] = Mock()
sys.modules['PyQt6.QtWidgets'] = Mock()
sys.modules['PyQt6.QtCore'] = Mock()
sys.modules['PyQt6.QtWidgets'].QTreeWidgetItem = MockQTreeWidgetItem
sys.modules['PyQt6.QtCore'].Qt = MockQt()

from ciclone.services.ui.electrode_view_delegate import ElectrodeViewDelegate
from ciclone.domain.electrodes import Electrode, Contact


class TestElectrodeViewDelegate(unittest.TestCase):
    """Test cases for ElectrodeViewDelegate."""
    
    def setUp(self):
        """Set up test environment."""
        self.delegate = ElectrodeViewDelegate()
    
    def test_create_tree_item_basic_electrode(self):
        """Test creating a tree item for a basic electrode."""
        # Arrange
        electrode = Electrode(name="TestElectrode", electrode_type="test")
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        
        # Assert
        self.assertIsNotNone(tree_item)
        self.assertEqual(tree_item.text(0), "TestElectrode")
        self.assertEqual(tree_item.childCount(), 0)  # No contacts
    
    def test_create_tree_item_with_contacts(self):
        """Test creating a tree item for an electrode with contacts."""
        # Arrange
        electrode = Electrode(name="TestElectrode", electrode_type="test")
        electrode.add_contact("T1", 10.5, 20.7, 30.2)
        electrode.add_contact("T2", 11.3, 21.9, 31.1)
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        
        # Assert
        self.assertIsNotNone(tree_item)
        self.assertEqual(tree_item.text(0), "TestElectrode")
        self.assertEqual(tree_item.childCount(), 2)
        
        # Check first contact
        contact1_item = tree_item.child(0)
        self.assertIsNotNone(contact1_item)
        self.assertEqual(contact1_item.text(0), "T1")
        self.assertEqual(contact1_item.text(1), "10")  # int conversion
        self.assertEqual(contact1_item.text(2), "20")  # int conversion
        self.assertEqual(contact1_item.text(3), "30")  # int conversion
        
        # Check second contact
        contact2_item = tree_item.child(1)
        self.assertIsNotNone(contact2_item)
        self.assertEqual(contact2_item.text(0), "T2")
        self.assertEqual(contact2_item.text(1), "11")
        self.assertEqual(contact2_item.text(2), "21")
        self.assertEqual(contact2_item.text(3), "31")
    
    def test_create_tree_item_coordinate_conversion(self):
        """Test that coordinates are properly converted to integers."""
        # Arrange
        electrode = Electrode(name="TestElectrode", electrode_type="test")
        electrode.add_contact("T1", 10.999, 20.001, 30.567)
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        contact_item = tree_item.child(0)
        
        # Assert
        self.assertEqual(contact_item.text(1), "10")  # 10.999 -> 10
        self.assertEqual(contact_item.text(2), "20")  # 20.001 -> 20
        self.assertEqual(contact_item.text(3), "30")  # 30.567 -> 30
    
    def test_create_tree_item_negative_coordinates(self):
        """Test handling of negative coordinates."""
        # Arrange
        electrode = Electrode(name="TestElectrode", electrode_type="test")
        electrode.add_contact("T1", -10.5, -20.7, -30.2)
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        contact_item = tree_item.child(0)
        
        # Assert
        self.assertEqual(contact_item.text(1), "-10")
        self.assertEqual(contact_item.text(2), "-20")
        self.assertEqual(contact_item.text(3), "-30")
    
    def test_create_tree_item_zero_coordinates(self):
        """Test handling of zero coordinates."""
        # Arrange
        electrode = Electrode(name="TestElectrode", electrode_type="test")
        electrode.add_contact("T1", 0.0, 0.0, 0.0)
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        contact_item = tree_item.child(0)
        
        # Assert
        self.assertEqual(contact_item.text(1), "0")
        self.assertEqual(contact_item.text(2), "0")
        self.assertEqual(contact_item.text(3), "0")
    
    def test_create_tree_item_empty_electrode_name(self):
        """Test creating tree item for electrode with empty name."""
        # Arrange
        electrode = Electrode(name="", electrode_type="test")
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        
        # Assert
        self.assertEqual(tree_item.text(0), "")
    
    def test_create_tree_item_special_characters_in_name(self):
        """Test creating tree item for electrode with special characters."""
        # Arrange
        electrode = Electrode(name="Test-Electrode_123", electrode_type="test")
        electrode.add_contact("T-1_A", 10.0, 20.0, 30.0)
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        contact_item = tree_item.child(0)
        
        # Assert
        self.assertEqual(tree_item.text(0), "Test-Electrode_123")
        self.assertEqual(contact_item.text(0), "T-1_A")
    
    def test_create_tree_item_many_contacts(self):
        """Test creating tree item for electrode with many contacts."""
        # Arrange
        electrode = Electrode(name="MultiContact", electrode_type="test")
        for i in range(10):
            electrode.add_contact(f"C{i}", float(i), float(i*10), float(i*100))
        
        # Act
        tree_item = self.delegate.create_tree_item(electrode)
        
        # Assert
        self.assertEqual(tree_item.childCount(), 10)
        
        # Check a few specific contacts
        first_contact = tree_item.child(0)
        self.assertEqual(first_contact.text(0), "C0")
        self.assertEqual(first_contact.text(1), "0")
        
        last_contact = tree_item.child(9)
        self.assertEqual(last_contact.text(0), "C9")
        self.assertEqual(last_contact.text(1), "9")
        self.assertEqual(last_contact.text(2), "90")
        self.assertEqual(last_contact.text(3), "900")
    
    def test_delegate_instance_isolation(self):
        """Test that multiple delegate instances work independently."""
        # Arrange
        delegate1 = ElectrodeViewDelegate()
        delegate2 = ElectrodeViewDelegate()
        
        electrode1 = Electrode(name="Electrode1", electrode_type="test")
        electrode2 = Electrode(name="Electrode2", electrode_type="test")
        
        # Act
        tree_item1 = delegate1.create_tree_item(electrode1)
        tree_item2 = delegate2.create_tree_item(electrode2)
        
        # Assert
        self.assertEqual(tree_item1.text(0), "Electrode1")
        self.assertEqual(tree_item2.text(0), "Electrode2")
        self.assertNotEqual(tree_item1, tree_item2)


if __name__ == '__main__':
    unittest.main()