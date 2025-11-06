"""
Flask Auto-Scaffold Generator
Automatically generates complete Flask blueprints from SQLAlchemy models.

Usage:
    python scaffold_generator.py

This will read models.py and generate:
- Blueprint folders (one per model)
- Forms (Flask-WTF)
- Routes (CRUD operations)
- Jinja2 templates and macros
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Type
from datetime import datetime, date
from decimal import Decimal

try:
    from sqlalchemy import inspect as sa_inspect, Integer, String, Text, Boolean, Date, DateTime, Float, Numeric
    from sqlalchemy.orm import DeclarativeBase
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    print("SQLAlchemy not found. Please install: pip install sqlalchemy")
    exit(1)


class ScaffoldGenerator:
    """Main generator class for scaffolding Flask applications."""
    
    # Type mapping for SQLAlchemy to WTForms
    TYPE_MAPPING = {
        'String': 'StringField',
        'Text': 'TextAreaField',
        'Integer': 'IntegerField',
        'BigInteger': 'IntegerField',
        'SmallInteger': 'IntegerField',
        'Float': 'FloatField',
        'Numeric': 'DecimalField',
        'Boolean': 'BooleanField',
        'Date': 'DateField',
        'DateTime': 'DateTimeField',
    }
    
    def __init__(self, app_dir: str = 'app', base_dir: str = '.'):
        self.base_dir = Path(base_dir)
        self.app_dir = self.base_dir / app_dir
        self.templates_dir = self.app_dir / 'templates'
        self.models = []
        
    def discover_models(self):
        """Import and discover all SQLAlchemy models from models.py."""
        import sys
        import importlib.util
        
        # Add parent directory to path so we can import app
        sys.path.insert(0, str(self.base_dir))
        
        try:
            # Load models.py as a module
            models_path = self.app_dir / 'models.py'
            if not models_path.exists():
                print(f"Error: models.py not found at {models_path}")
                return
            
            spec = importlib.util.spec_from_file_location("models", models_path)
            models_module = importlib.util.module_from_spec(spec)
            
            # Mock the db object if import fails
            try:
                spec.loader.exec_module(models_module)
            except ImportError as e:
                print(f"Warning: Could not fully import models.py ({e})")
                print("Attempting to parse models manually...")
                self._parse_models_from_file(models_path)
                return
                
        except Exception as e:
            print(f"Error loading models: {e}")
            print("Attempting to parse models manually...")
            self._parse_models_from_file(self.app_dir / 'models.py')
            return
        
        # Find all SQLAlchemy model classes
        for name in dir(models_module):
            obj = getattr(models_module, name)
            if (isinstance(obj, type) and 
                hasattr(obj, '__tablename__') and 
                name not in ['Base', 'db']):
                self.models.append(obj)
        
        print(f"Discovered {len(self.models)} models: {[m.__name__ for m in self.models]}")
    
    def _get_table_name_for_model(self, model_name: str, all_models_info: Dict[str, Dict]) -> str:
        """Get the correct table name for a model by looking up its __tablename__."""
        # First, try to find the model in our parsed models
        for model in self.models:
            if hasattr(model, '__name__') and model.__name__ == model_name:
                if hasattr(model, '__tablename__'):
                    return model.__tablename__
                elif hasattr(model, '_parsed_info'):
                    return model._parsed_info['table_name']

        # Fallback: try to find it in all_models_info
        if model_name in all_models_info:
            return all_models_info[model_name]['table_name']

        # Last resort: guess the table name (common patterns)
        if model_name.endswith('s'):
            return model_name.lower() + 'es'  # class -> classes
        elif model_name.endswith('y'):
            return model_name[:-1].lower() + 'ies'  # category -> categories
        else:
            return model_name.lower() + 's'  # user -> users, project -> projects

    def _parse_models_from_file(self, models_path: Path):
        """Parse models.py file manually to extract model information."""
        import re  
        content = models_path.read_text()        
        # Find all class definitions that inherit from db.Model
        class_pattern = r'class\s+(\w+)\([^)]*db\.Model[^)]*\):'
        classes = re.findall(class_pattern, content)        
        for class_name in classes:
            # Extract class content
            class_pattern_detailed = rf'class\s+{class_name}\([^)]*\):(.+?)(?=\nclass\s|\Z)'
            match = re.search(class_pattern_detailed, content, re.DOTALL)            
            if not match:
                continue            
            class_content = match.group(1)            
            # Extract __tablename__
            tablename_match = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", class_content)
            if not tablename_match:
                continue            
            tablename = tablename_match.group(1)            
            # Extract columns - IMPROVED REGEX to handle nested parentheses
            # This will match db.Column(...) including nested function calls
            column_lines = re.findall(r'^\s*(\w+)\s*=\s*db\.Column\((.*?)\)(?:\s*$|\s*\n)', 
                                      class_content, re.MULTILINE)            
            # For lines where the simple regex doesn't work, try a more complex approach
            if not column_lines or len(column_lines) < 3:  # Heuristic: most models have at least a few columns
                # Parse line by line for better accuracy
                lines = class_content.split('\n')
                column_lines = []
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if '= db.Column(' in line:
                        # Extract column name
                        col_match = re.match(r'(\w+)\s*=\s*db\.Column\((.*)', line)
                        if col_match:
                            col_name = col_match.group(1)
                            col_def_start = col_match.group(2)                            
                            # Count parentheses to find where Column definition ends
                            paren_count = 1  # We already have the opening paren from db.Column(
                            col_def_parts = [col_def_start]                            
                            for char in col_def_start:
                                if char == '(':
                                    paren_count += 1
                                elif char == ')':
                                    paren_count -= 1                            
                            # If parentheses don't balance, continue to next lines
                            j = i + 1
                            while paren_count > 0 and j < len(lines):
                                next_line = lines[j].strip()
                                col_def_parts.append(next_line)
                                for char in next_line:
                                    if char == '(':
                                        paren_count += 1
                                    elif char == ')':
                                        paren_count -= 1
                                    if paren_count == 0:
                                        break
                                j += 1                           
                            # Join all parts and remove the final closing paren
                            full_col_def = ' '.join(col_def_parts).rstrip(')')
                            column_lines.append((col_name, full_col_def))
                            i = j
                            continue
                    i += 1            
            fields = {}
            user_fk_field = None
            non_user_fk_count = 0
            foreign_key_relationships = []  # ← NEW: Track FK relationships
            relationships = []  # ← NEW: Track db.relationship() declarations

            for col_name, col_def in column_lines:
                # Parse column definition
                field_info = self._parse_column_definition(col_name, col_def)
                fields[col_name] = field_info              
                # Check for foreign keys
                if 'ForeignKey' in col_def:
                    # Extract the referenced table and column
                    fk_match = re.search(r"ForeignKey\(['\"](\w+)\.(\w+)['\"]\)", col_def)
                    if fk_match:
                        ref_table = fk_match.group(1)
                        ref_column = fk_match.group(2)

                        is_user_fk = ref_table == 'users'

                        if is_user_fk:
                            user_fk_field = col_name
                            print(f"  → Found user FK: {col_name}")  # DEBUG
                        else:
                            non_user_fk_count += 1
                            # Store the relationship info
                            foreign_key_relationships.append({
                                'field_name': col_name,
                                'ref_table': ref_table,
                                'ref_column': ref_column
                            })            
            # Parse db.relationship() declarations
            relationship_lines = re.findall(r'^\s*(\w+)\s*=\s*db\.relationship\((.*?)\)',
                                          class_content, re.MULTILINE | re.DOTALL)

            for rel_name, rel_def in relationship_lines:
                # Extract the target model from relationship definition
                target_match = re.search(r"'(\w+)'", rel_def)
                if target_match:
                    target_model = target_match.group(1)

                    # Check for backref or back_populates
                    backref_match = re.search(r'backref\s*=\s*[\'"](\w+)[\'"]', rel_def)
                    back_populates_match = re.search(r'back_populates\s*=\s*[\'"](\w+)[\'"]', rel_def)

                    # Check for many-to-many relationship (secondary table)
                    secondary_match = re.search(r'secondary\s*=\s*[\'"]?(\w+)[\'"]?', rel_def)

                    relationships.append({
                        'name': rel_name,
                        'target_model': target_model,
                        'backref': backref_match.group(1) if backref_match else None,
                        'back_populates': back_populates_match.group(1) if back_populates_match else None,
                        'is_many_to_many': bool(secondary_match),  # NEW: Track many-to-many
                        'secondary_table': secondary_match.group(1) if secondary_match else None
                    })

            # Check for missing foreign keys based on relationships
            missing_fks = []
            for rel in relationships:
                # SKIP many-to-many relationships - they use association tables, not FK columns
                if rel.get('is_many_to_many', False):
                    print(f"  → Skipping many-to-many relationship: {rel['name']} -> {rel['target_model']} (uses {rel['secondary_table']})")
                    continue

                # Get the correct table name using our helper method
                target_table = self._get_table_name_for_model(rel['target_model'], {})

                # Determine expected foreign key column name
                # If this model has a backref on the relationship, the FK should be on this model
                # The FK column name should be: backref_name + '_id'
                if rel['backref']:
                    expected_fk_col = f"{rel['backref']}_id"
                elif rel['back_populates']:
                    expected_fk_col = f"{rel['back_populates']}_id"
                else:
                    # If no backref/back_populates, use the target table name + '_id'
                    expected_fk_col = f"{target_table}_id"

                # Skip if this relationship already has a corresponding FK column
                has_corresponding_fk = any(
                    fk['ref_table'] == target_table for fk in foreign_key_relationships
                )

                if has_corresponding_fk:
                    print(f"  → Relationship {rel['name']} already has FK to {target_table}")
                    continue

                # Check if the expected foreign key column exists
                if expected_fk_col not in fields:
                    missing_fks.append({
                        'relationship_name': rel['name'],
                        'target_model': rel['target_model'],
                        'missing_fk_column': expected_fk_col,
                        'target_table': target_table
                    })
                    print(f"  → Missing FK detected: {expected_fk_col} -> {target_table}.id (from relationship {rel['name']})")
                else:
                    print(f"  → FK already exists: {expected_fk_col} (from relationship {rel['name']})")

            # Create mock model info
            model_info = {
                'name': class_name,
                'table_name': tablename,
                'fields': fields,
                'primary_key': next((name for name, info in fields.items() if info.get('primary_key')), 'id'),
                'user_fk_field': user_fk_field,
                'non_user_fk_count': non_user_fk_count,
                'foreign_key_relationships': foreign_key_relationships,  # ← NEW
                'relationships': relationships,  # ← NEW
                'missing_foreign_keys': missing_fks  # ← NEW: Track missing FKs
            }           
            # DEBUG
            print(f"  DEBUG {class_name}: user_fk_field={user_fk_field}, non_user_fk_count={non_user_fk_count}")            
            # Store as dict instead of class for manual parsing
            self.models.append(type('Model', (), {
                '__name__': class_name,
                '__tablename__': tablename,
                '_parsed_info': model_info
            }))
        
        print(f"Parsed {len(self.models)} models from file: {[m.__name__ for m in self.models]}")
    
    def _parse_column_definition(self, col_name: str, col_def: str) -> Dict[str, Any]:
        """Parse a SQLAlchemy column definition string."""
        field_info = {
            'name': col_name,
            'type': 'String',
            'nullable': True,
            'primary_key': False,
            'default': None,
            'unique': False,
        }
        
        # Determine type
        if 'db.Integer' in col_def:
            field_info['type'] = 'Integer'
        elif 'db.String' in col_def:
            field_info['type'] = 'String'
            # Extract length
            length_match = re.search(r'db\.String\((\d+)\)', col_def)
            if length_match:
                field_info['max_length'] = int(length_match.group(1))
        elif 'db.Text' in col_def:
            field_info['type'] = 'Text'
        elif 'db.Boolean' in col_def:
            field_info['type'] = 'Boolean'
        elif 'db.DateTime' in col_def:
            field_info['type'] = 'DateTime'
        elif 'db.Date' in col_def:
            field_info['type'] = 'Date'
        elif 'db.Float' in col_def:
            field_info['type'] = 'Float'
        elif 'db.Numeric' in col_def:
            field_info['type'] = 'Numeric'
        
        # Check for primary_key
        if 'primary_key=True' in col_def:
            field_info['primary_key'] = True
        
        # Check for nullable
        if 'nullable=False' in col_def:
            field_info['nullable'] = False
        
        # Check for unique
        if 'unique=True' in col_def:
            field_info['unique'] = True
            
        # Check for default
        if 'default=datetime.utcnow' in col_def:
            field_info['default'] = 'datetime.utcnow' # Store as string
        
        # Skip ForeignKey columns in forms
        if 'ForeignKey' in col_def:
            field_info['skip_in_form'] = True
        
        return field_info
    
    def extract_model_info(self, model: Type) -> Dict[str, Any]:
        """Extract field information from SQLAlchemy model."""
        # Check if this is a parsed model (has _parsed_info)
        if hasattr(model, '_parsed_info'):
            return model._parsed_info
        
        # Otherwise, introspect the actual model
        mapper = sa_inspect(model)
        fields = {}
        primary_key = None
        user_fk_field = None 
        non_user_fk_count = 0 
        
        for column in mapper.columns:
            field_info = {
                'name': column.name,
                'type': column.type.__class__.__name__,
                'nullable': column.nullable,
                'primary_key': column.primary_key,
                'default': column.default,
                'unique': column.unique,
            }
            
            # Track primary key
            if column.primary_key:
                primary_key = column.name
            
            # Get max length for string fields
            if hasattr(column.type, 'length') and column.type.length:
                field_info['max_length'] = column.type.length
            
            # Check for foreign keys
            if column.foreign_keys:
                field_info['skip_in_form'] = True

                is_user_fk = False
                # Check all foreign keys on this column
                for fk in column.foreign_keys:
                    if str(fk.column) == 'users.id':
                        is_user_fk = True
                    else:
                        # It's a foreign key, but not to 'users.id'
                        non_user_fk_count += 1

                if is_user_fk:
                    user_fk_field = column.name

            fields[column.name] = field_info

        # Extract foreign key relationships for live models
        foreign_key_relationships = []
        for column in mapper.columns:
            if column.foreign_keys:
                for fk in column.foreign_keys:
                    fk_parts = str(fk.column).split('.')
                    if len(fk_parts) == 2:
                        ref_table = fk_parts[0]
                        ref_column = fk_parts[1]
                        if ref_table != 'users':  # Skip user FKs
                            foreign_key_relationships.append({
                                'field_name': column.name,
                                'ref_table': ref_table,
                                'ref_column': ref_column
                            })

        # Extract relationships for live models using SQLAlchemy inspection
        relationships = []
        if hasattr(model, '__mapper__') and hasattr(model.__mapper__, 'relationships'):
            for rel in model.__mapper__.relationships:
                # Get the target model name
                target_model = rel.entity.class_.__name__ if hasattr(rel.entity, 'class_') else str(rel.entity)

                # Check for backref or back_populates
                backref = getattr(rel, 'backref', None)
                back_populates = getattr(rel, 'back_populates', None)

                # Check for many-to-many relationship (secondary table)
                secondary = getattr(rel, 'secondary', None)

                relationships.append({
                    'name': rel.key,
                    'target_model': target_model,
                    'backref': backref,
                    'back_populates': back_populates,
                    'is_many_to_many': secondary is not None,  # NEW: Track many-to-many
                    'secondary_table': getattr(secondary, 'name', None) if secondary else None
                })

        # Check for missing foreign keys based on relationships
        missing_fks = []
        for rel in relationships:
            # SKIP many-to-many relationships - they use association tables, not FK columns
            if rel.get('is_many_to_many', False):
                print(f"  → Skipping many-to-many relationship: {rel['name']} -> {rel['target_model']} (uses {rel['secondary_table']})")
                continue

            # Get the correct table name using our helper method
            target_table = self._get_table_name_for_model(rel['target_model'], {})

            # Determine expected foreign key column name
            # If this model has a backref on the relationship, the FK should be on this model
            # The FK column name should be: backref_name + '_id'
            if rel['backref']:
                expected_fk_col = f"{rel['backref']}_id"
            elif rel['back_populates']:
                expected_fk_col = f"{rel['back_populates']}_id"
            else:
                # If no backref/back_populates, use the target table name + '_id'
                expected_fk_col = f"{target_table}_id"

            # Skip if this relationship already has a corresponding FK column
            has_corresponding_fk = any(
                fk['ref_table'] == target_table for fk in foreign_key_relationships
            )

            if has_corresponding_fk:
                print(f"  → Relationship {rel['name']} already has FK to {target_table}")
                continue

            # Check if the expected foreign key column exists
            if expected_fk_col not in fields:
                missing_fks.append({
                    'relationship_name': rel['name'],
                    'target_model': rel['target_model'],
                    'missing_fk_column': expected_fk_col,
                    'target_table': target_table
                })
                print(f"  → Missing FK detected: {expected_fk_col} -> {target_table}.id (from relationship {rel['name']})")
            else:
                print(f"  → FK already exists: {expected_fk_col} (from relationship {rel['name']})")

        print(f"DEBUG {model.__name__}: user_fk_field={user_fk_field}, non_user_fk_count={non_user_fk_count}")
        if missing_fks:
            print(f"  WARNING {model.__name__}: Missing foreign keys: {[fk['missing_fk_column'] for fk in missing_fks]}")

        return {
            'name': model.__name__,
            'table_name': model.__tablename__,
            'fields': fields,
            'primary_key': primary_key or 'id',
            'user_fk_field': user_fk_field,
            'non_user_fk_count': non_user_fk_count,
            'foreign_key_relationships': foreign_key_relationships,
            'relationships': relationships,  # ← NEW
            'missing_foreign_keys': missing_fks  # ← NEW
        }

    def _find_child_models(self, parent_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find all models that reference this model via foreign key."""
        parent_table = parent_info['table_name']
        child_models = []

        for model in self.models:
            model_info = self.extract_model_info(model)

            # Check if this model has foreign key relationships to the parent
            if 'foreign_key_relationships' in model_info:
                for fk_rel in model_info['foreign_key_relationships']:
                    if fk_rel['ref_table'] == parent_table:
                        child_models.append({
                            'name': model_info['name'],
                            'table_name': model_info['table_name'],
                            'primary_key': model_info['primary_key'],
                            'fk_field': fk_rel['field_name'],
                            'user_fk_field': model_info.get('user_fk_field'),
                            'fields': model_info['fields']
                        })
                        break  # Only add once even if multiple FKs exist

        return child_models

    def generate_forms_file(self, model_info: Dict[str, Any], blueprint_dir: Path):
        """Generate forms.py for a model."""
        model_name = model_info['name']
        fields = model_info['fields']
        
        # Generate field definitions
        field_lines = []
        for field_name, field_info in fields.items():
            # Skip primary keys and foreign keys
            if field_info.get('primary_key') or field_info.get('skip_in_form'):
                continue
            
            # Skip DateTime fields that have a default of datetime.utcnow
            is_datetime_utc_default = False
            if field_info['type'] == 'DateTime' and field_info['default'] is not None:
                # Check for live model object (column.default.arg == datetime.utcnow)
                if (hasattr(field_info['default'], 'arg') and
                    field_info['default'].arg == datetime.utcnow):
                    is_datetime_utc_default = True
                # Check for parsed model string
                elif field_info['default'] == 'datetime.utcnow':
                    is_datetime_utc_default = True

            if is_datetime_utc_default:
                continue
            
            wtf_type = self.TYPE_MAPPING.get(field_info['type'], 'StringField')
            validators = []
            
            # --- UPDATED LOGIC ---
            # Handle BooleanField: always optional
            if field_info['type'] == 'Boolean':
                validators.append('Optional()')
            # Handle other fields
            elif not field_info['nullable']:
                validators.append('DataRequired()')
            else:
                validators.append('Optional()')
            # --- END UPDATED LOGIC ---
            
            # Add length validator for strings
            if 'max_length' in field_info and field_info['max_length']:
                validators.append(f"Length(max={field_info['max_length']})")
            
            # Special field handling - be more specific to avoid false matches
            if field_name.lower().endswith('email') or 'email_address' in field_name.lower():
                wtf_type = 'EmailField'
                if 'Email()' not in validators: # Avoid duplicates
                    validators.append('Email()')
            elif field_name.lower().endswith('url') or 'website' in field_name.lower():
                wtf_type = 'URLField'
                if 'URL()' not in validators:
                    validators.append('URL()')
            elif field_name.lower().endswith('password') or 'pwd' in field_name.lower():
                wtf_type = 'PasswordField'
            
            validators_str = ', '.join(validators)
            label = field_name.replace('_', ' ').title()
            
            field_lines.append(
                f"    {field_name} = {wtf_type}('{label}', validators=[{validators_str}])"
            )
        
        forms_content = f'''"""
Forms for {model_name} model.
Auto-generated by Flask Scaffold Generator.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, FloatField, BooleanField,
    DateField, DateTimeField, TextAreaField, DecimalField,
    PasswordField, EmailField, URLField, SubmitField
)
from wtforms.validators import DataRequired, Optional, Length, Email, URL


class {model_name}Form(FlaskForm):
    """Form for creating/editing {model_name}."""
{chr(10).join(field_lines)}
    submit = SubmitField('Submit')
'''
        
        forms_file = blueprint_dir / 'forms.py'
        forms_file.write_text(forms_content)
        print(f"  ✓ Generated {forms_file}")
    
    def generate_routes_file(self, model_info: Dict[str, Any], blueprint_dir: Path):
        """Generate routes.py with CRUD operations."""
        model_name = model_info['name']
        blueprint_name = model_info['table_name']
        pk_field = model_info['primary_key']
        user_fk_field = model_info.get('user_fk_field') 
        non_user_fk_count = model_info.get('non_user_fk_count', 0) 
        
        # Get display fields (non-pk fields, max 5)
        display_fields = [f for f in model_info['fields'].keys()
                         if not model_info['fields'][f].get('primary_key') and
                         not model_info['fields'][f].get('skip_in_form')][:5]

        # Check if this model is referenced by other models (it's a parent)
        child_models = self._find_child_models(model_info)

        # Generate child model queries for the view route
        view_route_child_queries = ""
        view_template_child_params = ""
        for child_info in child_models:
            child_table = child_info['table_name']
            child_name = child_info['name']
            fk_field = child_info['fk_field']
            view_route_child_queries += f'''
    # Get all {child_table} for this {model_name}
    {child_table} = {child_name}.query.filter_by({fk_field}={pk_field}).all()'''

            # Add to template parameters
            view_template_child_params += f'''
        {child_table}={child_table},'''

        # Generate additional routes for child management
        additional_child_routes = ""
        for child_info in child_models:
            child_routes = self.generate_parent_child_routes(model_info, child_info,
                                                          child_info['fk_field'], blueprint_dir)
            additional_child_routes += child_routes

        # Build import string that includes child models
        model_imports = [model_name]
        for child_info in child_models:
            if child_info['name'] not in model_imports:
                model_imports.append(child_info['name'])
        model_import_string = ', '.join(model_imports)

        # --- Create Route Generation ---
        create_route_content = ""
        if non_user_fk_count > 0:
            # This is a "child" model (like Comment) that depends on a parent (like Product).
            # A simple /create route is not feasible as it lacks the parent's ID.
            create_route_content = f'''
# --- NOTE: 'create' route commented out by scaffold generator ---
# This model appears to be a "child" model (it has {non_user_fk_count} foreign key(s)
# to models other than User). A simple '/create' route is not
# practical because it requires context from a "parent" object
# (e.g., a Comment needs a Product ID).
#
# You should handle the creation of this object within the
# "view" or "edit" route of its parent model.
# (e.g., add a comment form to the 'view_product' page).
#
#
# @{blueprint_name}_bp.route('/create', methods=['GET', 'POST'])
# @login_required
# def create_{blueprint_name}():
#     """Create a new {model_name}."""
#     form = {model_name}Form()
#     
#     if form.validate_on_submit():
#         try:
#             item = {model_name}()
#             form.populate_obj(item)
#             
#             # This would require parent IDs from the URL, e.g.:
#             # item.product_id = request.args.get('product_id')
#             {f"item.{user_fk_field} = current_user.id" if user_fk_field else ""}
#             
#             db.session.add(item)
#             db.session.commit()
#             
#             flash('{model_name} created successfully!', 'success')
#             return redirect(url_for('{blueprint_name}.list_{blueprint_name}'))
#         except Exception as e:
#             db.session.rollback()
#             flash(f'Error creating {model_name}: {{{{str(e)}}}}', 'danger')
#     
#     return render_template(
#         '{blueprint_name}/form.html',
#         form=form,
#         title='Create {model_name}',
#         action='create'
#     )
'''
        else:
            # This is a "top-level" model (like Task or User).
            # A simple /create route is fine.
            create_route_content = f'''
@{blueprint_name}_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_{blueprint_name}():
    """Create a new {model_name}."""
    form = {model_name}Form()
    
    if form.validate_on_submit():
        try:
            item = {model_name}()
            form.populate_obj(item)
            
            {f"item.{user_fk_field} = current_user.id" if user_fk_field else "# No user_fk_field found matching 'users.id'"}
            
            db.session.add(item)
            db.session.commit()
            
            flash('{model_name} created successfully!', 'success')
            return redirect(url_for('{blueprint_name}.list_{blueprint_name}'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating {model_name}: {{{{str(e)}}}}', 'danger')
    
    return render_template(
        '{blueprint_name}/form.html',
        form=form,
        title='Create {model_name}',
        action='create'
    )
'''
        
        # --- NEW: Security Check Snippets ---
        # Create a re-usable security check block
        security_check_block = ""
        if user_fk_field:
            security_check_block = f'''
    # Security check: ensure the current user owns this item
    if item.{user_fk_field} != current_user.id:
        flash('You do not have permission to access this item.', 'danger')
        return redirect(url_for('{blueprint_name}.list_{blueprint_name}'))
    '''

        list_query = f"items = {model_name}.query.all()"
        if user_fk_field:
            # If the model belongs to a user, only list their items
            list_query = f"items = {model_name}.query.filter_by({user_fk_field}=current_user.id).all()"
        
        
        # --- Full Routes File Content ---
        routes_content = f'''"""
Routes for {model_name} blueprint.
Auto-generated by Flask Scaffold Generator.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import {model_import_string}
from .forms import {model_name}Form


{blueprint_name}_bp = Blueprint(
    '{blueprint_name}',
    __name__,
    url_prefix='/{blueprint_name}',
    template_folder='../templates/{blueprint_name}'
)


@{blueprint_name}_bp.route('/')
@login_required
def list_{blueprint_name}():
    """List all {model_name} records."""
    {list_query}
    return render_template(
        '{blueprint_name}/list.html',
        items=items,
        model_name='{model_name}'
    )

{create_route_content}

@{blueprint_name}_bp.route('/<int:{pk_field}>')
@login_required
def view_{blueprint_name}({pk_field}):
    """View a single {model_name}."""
    item = {model_name}.query.get_or_404({pk_field})
    {security_check_block}
{view_route_child_queries}
    return render_template(
        '{blueprint_name}/view.html',
        item=item,
        model_name='{model_name}',{view_template_child_params}
    )


@{blueprint_name}_bp.route('/<int:{pk_field}>/edit', methods=['GET', 'POST'])
@login_required
def edit_{blueprint_name}({pk_field}):
    """Edit an existing {model_name}."""
    item = {model_name}.query.get_or_404({pk_field})
    {security_check_block}
    form = {model_name}Form(obj=item)
    
    if form.validate_on_submit():
        try:
            form.populate_obj(item)
            db.session.commit()
            
            flash('{model_name} updated successfully!', 'success')
            return redirect(url_for('{blueprint_name}.view_{blueprint_name}', {pk_field}={pk_field}))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating {model_name}: {{{{str(e)}}}}', 'danger')
    
    return render_template(
        '{blueprint_name}/form.html',
        form=form,
        title=f'Edit {model_name}',
        action='edit',
        item=item
    )


@{blueprint_name}_bp.route('/<int:{pk_field}>/delete', methods=['POST'])
@login_required
def delete_{blueprint_name}({pk_field}):
    """Delete a {model_name}."""
    item = {model_name}.query.get_or_404({pk_field})
    {security_check_block}
    try:
        db.session.delete(item)
        db.session.commit()
        flash('{model_name} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting {model_name}: {{{{str(e)}}}}', 'danger')
    
    return redirect(url_for('{blueprint_name}.list_{blueprint_name}'))
{additional_child_routes}
'''

        # Format the routes content with all variables
        try:
            formatted_routes_content = routes_content.format(
                model_name=model_name,
                blueprint_name=blueprint_name,
                pk_field=pk_field,
                user_fk_field=user_fk_field,
                non_user_fk_count=non_user_fk_count,
                table_fields=display_fields[:5],  # Limit to first 5 fields for table
                display_fields=display_fields,
                create_route_content=create_route_content,
                list_query=list_query,
                security_check_block=security_check_block,
                view_route_child_queries=view_route_child_queries,
                view_template_child_params=view_template_child_params,
                additional_child_routes=additional_child_routes,
                model_import_string=model_import_string
            )
        except KeyError as e:
            print(f"DEBUG: KeyError formatting routes for {model_name}: {e}")
            print(f"DEBUG: Available variables: model_name={model_name}, blueprint_name={blueprint_name}")
            print(f"DEBUG: display_fields={display_fields}")
            print(f"DEBUG: child_models={child_models}")
            # Show all lines with potential template variables
            lines = routes_content.split('\n')
            print("DEBUG: Searching for problematic template variables...")
            for i, line in enumerate(lines):
                if '{' in line and '}' in line and not line.strip().startswith('#'):
                    # Check if it contains unescaped braces
                    if '{{' not in line and '{%' not in line:
                        print(f"DEBUG: Potential issue at line {i+1}: {line.strip()}")
                        # Show what variable it's looking for
                        import re
                        matches = re.findall(r'\{([^}]+)\}', line)
                        for match in matches:
                            print(f"  -> Looking for variable: '{match}'")
            raise

        routes_file = blueprint_dir / 'routes.py'
        routes_file.write_text(formatted_routes_content)
        print(f"  ✓ Generated {routes_file}")

    def generate_parent_child_routes(self, parent_info: Dict, child_info: Dict,
                                  fk_field: str, parent_blueprint_dir: Path):
        """Generate routes for managing child objects from parent view."""
        parent_name = parent_info['name']
        parent_table = parent_info['table_name']
        parent_pk = parent_info['primary_key']

        child_name = child_info['name']
        child_table = child_info['table_name']
        child_pk = child_info['primary_key']
        user_fk_field = child_info.get('user_fk_field')

        # Generate singular name for routes (e.g., "products" -> "product")
        child_table_singular_name = child_table[:-1] if child_table.endswith('s') else child_table

        # This gets appended to the parent's routes.py
        additional_routes = f'''

# ============================================================
# Child Management: {child_name} within {parent_name}
# ============================================================

@{parent_table}_bp.route('/<int:{parent_pk}>/add-{child_table_singular_name}', methods=['GET', 'POST'])
@login_required
def add_{child_table}_to_{parent_table}({parent_pk}):
    """Add a {child_name} to this {parent_name}."""
    parent = {parent_name}.query.get_or_404({parent_pk})

    # Import child form (model already imported at top)
    from {child_table}.forms import {child_name}Form

    form = {child_name}Form()

    if form.validate_on_submit():
        try:
            item = {child_name}()
            form.populate_obj(item)

            # Set foreign keys
            item.{fk_field} = {parent_pk}
            {f"item.{user_fk_field} = current_user.id" if user_fk_field else ""}

            db.session.add(item)
            db.session.commit()

            flash('{child_name} added successfully!', 'success')
            return redirect(url_for('{parent_table}.view_{parent_table}', {parent_pk}={parent_pk}))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding {child_name}: {{{{str(e)}}}}', 'danger')

    return render_template(
        '{child_table}/form.html',
        form=form,
        title=f'Add {child_name} to {{{{ getattr(parent, 'name', getattr(parent, 'title', getattr(parent, 'company_name', getattr(parent, 'username', str(parent))))) }}}}',
        action='create'
    )
'''

        return additional_routes

    def generate_blueprint_init(self, model_info: Dict[str, Any], blueprint_dir: Path):
        """Generate __init__.py for blueprint."""
        blueprint_name = model_info['table_name']
        
        init_content = f'''"""
{model_info['name']} Blueprint
Auto-generated by Flask Scaffold Generator.
"""

from .routes import {blueprint_name}_bp

__all__ = ['{blueprint_name}_bp']
'''
        
        init_file = blueprint_dir / '__init__.py'
        init_file.write_text(init_content)
        print(f"  ✓ Generated {init_file}")
    
    def generate_templates(self, model_info: Dict[str, Any]):
        """Generate all templates for a model."""
        blueprint_name = model_info['table_name']
        model_name = model_info['name']
        pk_field = model_info['primary_key']
        non_user_fk_count = model_info.get('non_user_fk_count', 0)
        
        # Create template directories
        template_dir = self.templates_dir / blueprint_name
        template_dir.mkdir(parents=True, exist_ok=True)
        
        macros_dir = template_dir / 'macros'
        macros_dir.mkdir(exist_ok=True)
        
        # Get display fields
        display_fields = [f for f in model_info['fields'].keys() 
                         if not model_info['fields'][f].get('primary_key') and
                         not model_info['fields'][f].get('skip_in_form')]
        
        # Generate list.html
        self._generate_list_template(template_dir, model_info, display_fields, non_user_fk_count)
        
        # Generate form.html
        self._generate_form_template(template_dir, model_info, non_user_fk_count)
        
        # Generate view.html
        self._generate_view_template(template_dir, model_info)
        
        # Generate macros
        self._generate_macros(macros_dir, model_info)
    
    def _generate_list_template(self, template_dir: Path, model_info: Dict, display_fields: List[str], non_user_fk_count: int):
        """Generate list.html template."""
        blueprint_name = model_info['table_name']
        model_name = model_info['name']
        pk_field = model_info['primary_key']
        
        # Limit display fields to first 5
        table_fields = display_fields[:5]
        
        # Adjust "Create" button/text based on if it's a child model
        if non_user_fk_count > 0:
            create_button = f'''<!-- 'Create New' button disabled for child models -->
        <!-- You must create {model_name} records from a parent object's page. -->'''
            no_items_text = f'''<div class="alert alert-info">
            No {model_name} records found. These must be created from a parent object's page.
        </div>'''
        else:
            create_button = f'''<a href="{{{{ url_for('{blueprint_name}.create_{blueprint_name}') }}}}" class="btn btn-primary">
            <i class="bi bi-plus-circle"></i> Create New {model_name}
        </a>'''
            no_items_text = f'''<div class="alert alert-info">
            No {model_name} records found. <a href="{{{{ url_for('{blueprint_name}.create_{blueprint_name}') }}}}">Create one now</a>
        </div>'''

        
        list_template = f'''{{% extends "base.html" %}}
{{% import "{blueprint_name}/macros/display.html" as display %}}

{{% block title %}}{model_name} List{{% endblock %}}

{{% block content %}}
<div class="container mt-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1>{model_name} List</h1>
        {create_button}
    </div>

    {{% if items %}}
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead>
                    <tr>
                        {{% for field in {table_fields} %}}
                        <th>{{{{ field|replace('_', ' ')|title }}}}</th>
                        {{% endfor %}}
                        <th class="text-end">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {{% for item in items %}}
                    <tr>
                        {{% for field in {table_fields} %}}
                        <td>{{{{ display.format_value(item[field]) }}}}</td>
                        {{% endfor %}}
                        <td class="text-end">
                            <a href="{{{{ url_for('{blueprint_name}.view_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}" 
                               class="btn btn-sm btn-info">View</a>
                            <a href="{{{{ url_for('{blueprint_name}.edit_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}" 
                               class="btn btn-sm btn-warning">Edit</a>
                            <form method="POST" 
                                  action="{{{{ url_for('{blueprint_name}.delete_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}" 
                                  style="display:inline;"
                                  onsubmit="return confirm('Are you sure you want to delete this {model_name}?');">
                                <button type="submit" class="btn btn-sm btn-danger">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
        </div>
    {{% else %}}
        {no_items_text}
    {{% endif %}}
</div>
{{% endblock %}}
'''
        
        (template_dir / 'list.html').write_text(list_template)
        print(f"  ✓ Generated {template_dir}/list.html")
    
    def _generate_form_template(self, template_dir: Path, model_info: Dict, non_user_fk_count: int):
        """Generate form.html template."""
        blueprint_name = model_info['table_name']
        model_name = model_info['name']
        
        # Add a note if this is a child model, since the form won't work
        # from the commented-out /create route.
        child_model_note = ""
        if non_user_fk_count > 0:
            child_model_note = f'''
                    <div class="alert alert-warning">
                        <strong>Note:</strong> This form is for editing.
                        Creating new {model_name} records must be done from a parent object's page
                        to ensure it's correctly linked.
                    </div>
'''
        
        form_template = f'''{{% extends "base.html" %}}
{{% import "{blueprint_name}/macros/forms.html" as forms %}}

{{% block title %}}{{{{ title }}}}{{% endblock %}}

{{% block content %}}
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h2 class="mb-0">{{{{ title }}}}</h2>
                </div>
                <div class="card-body">
                    {child_model_note}
                    {{{{ forms.render_form(
                        form,
                        cancel_url=url_for('{blueprint_name}.list_{blueprint_name}')
                    ) }}}}
                </div>
            </div>
        </div>
    </div>
</div>
{{% endblock %}}
'''
        
        (template_dir / 'form.html').write_text(form_template)
        print(f"  ✓ Generated {template_dir}/form.html")
    
    def _generate_view_template(self, template_dir: Path, model_info: Dict):
        """Generate view.html template."""
        blueprint_name = model_info['table_name']
        model_name = model_info['name']
        pk_field = model_info['primary_key']

        # Check for child models
        child_models = self._find_child_models(model_info)

        child_sections = []
        for child_info in child_models:
            child_table = child_info['table_name']
            child_name = child_info['name']
            # Get first few display fields for the child
            display_fields = [f for f in child_info['fields'].keys()
                             if not child_info['fields'][f].get('primary_key')][:3]

            child_section = f'''
    <!-- {child_name} Section -->
    <div class="mt-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h2>{child_name}s in this {model_name}</h2>
            <a href="{{{{ url_for('{blueprint_name}.add_{child_table}_to_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}"
               class="btn btn-primary">
                <i class="bi bi-plus-circle"></i> Add {child_name}
            </a>
        </div>

        {{% if {child_table} %}}
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            {{% for field in {display_fields} %}}
                            <th>{{{{ field|replace('_', ' ')|title }}}}</th>
                            {{% endfor %}}
                            <th class="text-end">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {{% for child in {child_table} %}}
                        <tr>
                            {{% for field in {display_fields} %}}
                            <td>{{{{ child[field] }}}}</td>
                            {{% endfor %}}
                            <td class="text-end">
                                <a href="{{{{ url_for('{child_table}.view_{child_table}', id=child.id) }}}}"
                                   class="btn btn-sm btn-info">View</a>
                                <a href="{{{{ url_for('{child_table}.edit_{child_table}', id=child.id) }}}}"
                                   class="btn btn-sm btn-warning">Edit</a>
                            </td>
                        </tr>
                        {{% endfor %}}
                    </tbody>
                </table>
            </div>
        {{% else %}}
            <div class="alert alert-info">
                No {child_table} yet.
                <a href="{{{{ url_for('{blueprint_name}.add_{child_table}_to_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}">Add one now</a>
            </div>
        {{% endif %}}
    </div>'''

            child_sections.append(child_section)

        child_sections_html = ''.join(child_sections)

        view_template = f'''{{% extends "base.html" %}}
{{% import "{blueprint_name}/macros/display.html" as display %}}

{{% block title %}}{model_name} Details{{% endblock %}}

{{% block content %}}
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h1>{model_name} Details</h1>
                <div>
                    <a href="{{{{ url_for('{blueprint_name}.edit_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}"
                       class="btn btn-warning">Edit</a>
                    <a href="{{{{ url_for('{blueprint_name}.list_{blueprint_name}') }}}}"
                       class="btn btn-secondary">Back to List</a>
                </div>
            </div>

            <div class="card">
                <div class="card-body">
                    {{{{ display.display_model(item, exclude=['{pk_field}']) }}}}
                </div>
            </div>

            <div class="mt-3">
                <form method="POST"
                      action="{{{{ url_for('{blueprint_name}.delete_{blueprint_name}', {pk_field}=item.{pk_field}) }}}}"
                      onsubmit="return confirm('Are you sure you want to delete this {model_name}?');">
                    <button type="submit" class="btn btn-danger">Delete {model_name}</button>
                </form>
            </div>

            {child_sections_html}
        </div>
    </div>
</div>
{{% endblock %}}
'''
        
        (template_dir / 'view.html').write_text(view_template)
        print(f"  ✓ Generated {template_dir}/view.html")
    
    def _generate_macros(self, macros_dir: Path, model_info: Dict):
        """Generate Jinja2 macros for forms and display."""
        
        # Generate forms.html macro
        forms_macro = '''{% macro render_form(form, action="", method="post", submit_text="Submit", cancel_url=None) %}
<form method="{{ method }}" action="{{ action }}" novalidate>
    {{ form.hidden_tag() }}
    
    {% for field in form if field.widget.input_type != 'hidden' and field.name not in ['csrf_token', 'submit'] %}
        {{ render_field(field) }}
    {% endfor %}
    
    <div class="form-actions mt-4">
        {{ form.submit(class="btn btn-primary") }}
        {% if cancel_url %}
            <a href="{{ cancel_url }}" class="btn btn-secondary ms-2">Cancel</a>
        {% endif %}
    </div>
</form>
{% endmacro %}

{% macro render_field(field, label_visible=true) %}
<div class="mb-3 {% if field.errors %}has-error{% endif %}">
    {% if label_visible and field.type not in ['HiddenField', 'BooleanField'] %}
        {{ field.label(class="form-label") }}
    {% endif %}
    
    {% if field.type == 'BooleanField' %}
        <div class="form-check">
            {{ field(class="form-check-input" + (" is-invalid" if field.errors else "")) }}
            {{ field.label(class="form-check-label") }}
        </div>
    {% elif field.type == 'SelectField' %}
        {{ field(class="form-select" + (" is-invalid" if field.errors else "")) }}
    {% elif field.type == 'TextAreaField' %}
        {{ field(class="form-control" + (" is-invalid" if field.errors else ""), rows=4) }}
    {% else %}
        {{ field(class="form-control" + (" is-invalid" if field.errors else "")) }}
    {% endif %}
    
    {% if field.description %}
        <small class="form-text text-muted d-block mt-1">{{ field.description }}</small>
    {% endif %}
    
    {% if field.errors %}
        <div class="invalid-feedback d-block">
            {% for error in field.errors %}
                <span>{{ error }}</span>
            {% endfor %}
        </div>
    {% endif %}
</div>
{% endmacro %}
'''
        
        (macros_dir / 'forms.html').write_text(forms_macro)
        print(f"  ✓ Generated {macros_dir}/forms.html")
        
        # Generate display.html macro
        display_macro = '''{% macro display_model(obj, fields=None, exclude=None) %}
<dl class="row mb-0">
    {% if obj is mapping %}
        {% set items = obj.items() %}
    {% else %}
        {% set items = obj.__dict__.items() %}
    {% endif %}
    
    {% for key, value in items %}
        {% if not key.startswith('_') and (not fields or key in fields) and (not exclude or key not in exclude) %}
            <dt class="col-sm-4 text-muted">{{ key|replace('_', ' ')|title }}</dt>
            <dd class="col-sm-8">{{ format_value(value) }}</dd>
        {% endif %}
    {% endfor %}
</dl>
{% endmacro %}

{% macro format_value(value) %}
    {% if value is none %}
        <em class="text-muted">Not set</em>
    {% elif value is sameas true %}
        <span classall="badge bg-success">Yes</span>
    {% elif value is sameas false %}
        <span class="badge bg-secondary">No</span>
    {% elif value.__class__.__name__ == 'datetime' %}
        {{ value.strftime('%Y-%m-%d %H:%M:%S') }}
    {% elif value.__class__.__name__ == 'date' %}
        {{ value.strftime('%Y-%m-%d') }}
    {% elif value is iterable and value is not string and value is not mapping %}
        <ul class="list-unstyled mb-0">
            {% for item in value %}
                <li>{{ item }}</li>
            {% endfor %}
        </ul>
    {% else %}
        {{ value }}
    {% endif %}
{% endmacro %}
'''
        
        (macros_dir / 'display.html').write_text(display_macro)
        print(f"  ✓ Generated {macros_dir}/display.html")
    
    def generate_base_template(self):
        """Generate base.html if it doesn't exist."""
        base_template_path = self.templates_dir / 'base.html'
        
        if base_template_path.exists():
            print("  ℹ base.html already exists, skipping...")
            return
        
        base_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Flask App{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">Flask App</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    {% block nav_items %}{% endblock %}
                </ul>
                <ul class="navbar-nav ms-auto">
                    {% if current_user.is_authenticated %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('users.logout') }}">Logout</a>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('users.login') }}">Login</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <main>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="container mt-3">
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
'''
        
        base_template_path.write_text(base_template)
        print(f"  ✓ Generated {base_template_path}")
    
    def fix_missing_foreign_keys(self):
        """Add missing foreign key columns to models.py file."""
        models_path = self.app_dir / 'models.py'

        if not models_path.exists():
            print(f"  ⚠️  models.py not found at {models_path}")
            return

        # Read existing models.py content
        content = models_path.read_text()
        lines = content.split('\n')

        # Check each model for missing foreign keys
        for model in self.models:
            model_info = self.extract_model_info(model)
            missing_fks = model_info.get('missing_foreign_keys', [])

            if missing_fks:
                class_name = model_info['name']
                print(f"\n  Fixing missing foreign keys in {class_name}:")

                # Find the class definition in the file
                class_start = -1
                for i, line in enumerate(lines):
                    if line.strip().startswith(f'class {class_name}('):
                        class_start = i
                        break

                if class_start == -1:
                    print(f"    ⚠️  Could not find {class_name} class in models.py")
                    continue

                # Find the end of the class (next class or end of file)
                class_end = len(lines)
                for i in range(class_start + 1, len(lines)):
                    if lines[i].strip().startswith('class ') and not lines[i].strip().startswith('class '):
                        class_end = i
                        break

                # Find where to insert the missing foreign key columns
                # Look for the last db.Column definition in the class
                insert_index = class_start + 1
                last_column_index = class_start

                for i in range(class_start + 1, class_end):
                    if '= db.Column(' in lines[i]:
                        last_column_index = i

                if last_column_index > class_start:
                    insert_index = last_column_index + 1

                # Insert missing foreign key columns
                for missing_fk in missing_fks:
                    # Safety check: make sure this column doesn't already exist
                    column_exists = False
                    for line in lines[class_start:class_end]:
                        if f"{missing_fk['missing_fk_column']} = db.Column(" in line:
                            column_exists = True
                            break

                    if column_exists:
                        print(f"    ⚠️  Column {missing_fk['missing_fk_column']} already exists, skipping...")
                        continue

                    fk_line = f"    {missing_fk['missing_fk_column']} = db.Column(db.Integer, db.ForeignKey('{missing_fk['target_table']}.id'), nullable=False)"
                    lines.insert(insert_index, fk_line)
                    insert_index += 1
                    print(f"    ✓ Added {missing_fk['missing_fk_column']} foreign key column")

        # Write the updated content back to models.py
        updated_content = '\n'.join(lines)
        models_path.write_text(updated_content)
        print(f"\n  ✓ Updated models.py with missing foreign key columns")

    def update_app_file(self):
        """Generate instructions for updating app.py with new blueprints."""
        print("\n" + "="*60)
        print("SETUP INSTRUCTIONS")
        print("="*60)
        
        # Check if extensions.py exists
        extensions_file = self.app_dir / 'extensions.py'
        if not extensions_file.exists():
            print("\n⚠️  IMPORTANT: Create app/extensions.py first!")
            print("\nCreate this file to avoid circular imports:")
            print("-" * 60)
            print("""
# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
""")
            print("-" * 60)
            print("\nThen update app/models.py to import from extensions:")
            print("  Change: from app import db")
            print("  To:     from extensions import db")

    def add_user_model(self):
        """Add User model to models.py if it doesn't already exist."""
        models_path = self.app_dir / 'models.py'

        if not models_path.exists():
            print(f"  ⚠️  models.py not found at {models_path}")
            return

        # Read existing models.py content
        content = models_path.read_text()

        # Check if User model already exists
        if 'class User(UserMixin, db.Model):' in content:
            print("  ✓ User model already exists in models.py")
            return

        # Check for required imports
        required_imports = [
            'from flask_login import UserMixin',
            'from werkzeug.security import generate_password_hash, check_password_hash'
        ]

        # Add missing imports
        lines = content.split('\n')
        import_lines = []
        existing_imports = set()

        # Find existing imports
        for line in lines:
            if line.strip().startswith('from ') or line.strip().startswith('import '):
                existing_imports.add(line.strip())

        # Add required imports if they don't exist
        for import_line in required_imports:
            if import_line not in existing_imports:
                import_lines.append(import_line)

        if import_lines:
            # Find the last import line and add new imports after it
            last_import_index = -1
            for i, line in enumerate(lines):
                if line.strip().startswith('from ') or line.strip().startswith('import '):
                    last_import_index = i

            if last_import_index >= 0:
                # Insert after the last import
                lines[last_import_index+1:last_import_index+1] = import_lines + ['']
            else:
                # Add at the beginning if no imports found
                lines[0:0] = import_lines + ['']

        # Add User model at the end of the file
        user_model_code = '''

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
'''

        # Append the User model
        lines.append(user_model_code)

        # Write the updated content back to models.py
        updated_content = '\n'.join(lines)
        models_path.write_text(updated_content)
        print("  ✓ Added User model to models.py")

        print("\n  ℹ️  Note: Make sure you have the required dependencies:")
        print("     pip install flask-login werkzeug")

        print("\n  ℹ️  Remember to update your app.py to include:")
        print("     from models import User")
        print("     @login_manager.user_loader")
        print("     def load_user(user_id):")
        print("         return User.query.get(int(user_id))")

        print("\n" + "="*60)
        print("BLUEPRINT REGISTRATION")
        print("="*60)
        print("\nAdd these imports INSIDE create_app() function (after app is created):")
        print("-" * 60)
        
        for model in self.models:
            blueprint_name = model.__tablename__
            print(f"from {blueprint_name} import {blueprint_name}_bp")
        
        print("\nAdd these registrations in create_app():")
        print("-" * 60)
        for model in self.models:
            blueprint_name = model.__tablename__
            print(f"app.register_blueprint({blueprint_name}_bp)")
        
        print("\n" + "="*60)
        print("Example app.py structure:")
        print("="*60)
        print("""
from flask import Flask
from flask_cors import CORS
from extensions import db, login_manager  # Import from extensions
# Make sure to import your User model for the user_loader
from models import User

def create_app():
    app = Flask(__name__)

    # ... app configuration ...

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Import blueprints HERE (after app creation)
    # Example:
    # from auth import auth as auth_blueprint
    # app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # Add your generated blueprints:
    from users import users_bp
    from tasks import tasks_bp
    from categories import categories_bp
    from products import products_bp

    # Register blueprints
    app.register_blueprint(users_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(products_bp)

    return app

# Note: The User model has been automatically added to your models.py file
# with required imports (UserMixin, werkzeug security functions)
""")
        
    def run(self):
        """Main execution method."""
        print("="*60)
        print("Flask Auto-Scaffold Generator")
        print("="*60)
        
        # Discover models
        print("\n1. Discovering models...")
        self.discover_models()
        
        if not self.models:
            print("No models found. Exiting.")
            return
        
        # Generate base template
        print("\n2. Generating base template...")
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.generate_base_template()
        
        # Generate for each model
        print("\n3. Generating blueprints...")
        for model in self.models:
            model_info = self.extract_model_info(model)
            blueprint_name = model_info['table_name']
            
            print(f"\n  Processing {model_info['name']}:")
            
            # Create blueprint directory
            blueprint_dir = self.app_dir / blueprint_name
            blueprint_dir.mkdir(exist_ok=True)
            
            # Generate files
            self.generate_forms_file(model_info, blueprint_dir)
            self.generate_routes_file(model_info, blueprint_dir)
            self.generate_blueprint_init(model_info, blueprint_dir)
            
            # Generate templates
            print(f"  Generating templates for {blueprint_name}:")
            self.generate_templates(model_info)
        
        # Fix missing foreign keys before generating blueprints
        print("\n4. Checking for missing foreign keys...")
        self.fix_missing_foreign_keys()

        # Add User model to models.py if it doesn't exist
        print("\n5. Adding User model...")
        self.add_user_model()

        # Show blueprint registration instructions
        self.update_app_file()

        print("\n" + "="*60)
        print("✓ Scaffold generation complete!")
        print("="*60)


if __name__ == '__main__':
    generator = ScaffoldGenerator()
    generator.run()

