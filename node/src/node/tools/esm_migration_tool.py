# tools/esm_migration_tool.py
"""
Tool for gradual CommonJS to ESM migration with hybrid support
"""

from crewai_tools import BaseTool
from pydantic import BaseModel, Field
import re
import json
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class ESMMigrationInput(BaseModel):
    project_path: str = Field(..., description="Root path of the project")
    strategy: str = Field(default="hybrid", description="Migration strategy: full, hybrid, or gradual")
    
class ESMMigrationTool(BaseTool):
    name: str = "ESM Migration Tool"
    description: str = "Migrates CommonJS to ESM with support for legacy code"
    args_schema: type[BaseModel] = ESMMigrationInput
    
    def _run(self, project_path: str, strategy: str = "hybrid") -> Dict:
        """Execute ESM migration with chosen strategy"""
        
        project = Path(project_path)
        if not project.exists():
            return {"error": f"Project path not found: {project_path}"}
        
        # Analyze project structure and dependencies
        analysis = self._analyze_project_structure(project)
        
        # Determine migration order based on dependencies
        migration_order = self._determine_migration_order(analysis)
        
        # Apply migration strategy
        if strategy == "hybrid":
            result = self._apply_hybrid_strategy(project, analysis, migration_order)
        elif strategy == "gradual":
            result = self._apply_gradual_strategy(project, analysis, migration_order)
        elif strategy == "full":
            result = self._apply_full_migration(project, analysis, migration_order)
        else:
            return {"error": f"Unknown strategy: {strategy}"}
        
        # Generate compatibility shims
        shims = self._generate_compatibility_shims(analysis)
        
        # Create migration report
        report = self._create_migration_report(result, analysis)
        
        return {
            "status": "success",
            "strategy": strategy,
            "analysis": analysis,
            "migration_result": result,
            "compatibility_shims": shims,
            "report": report,
            "next_steps": self._get_next_steps(result)
        }
    
    def _analyze_project_structure(self, project: Path) -> Dict:
        """Analyze project for CommonJS/ESM patterns"""
        
        analysis = {
            "total_files": 0,
            "commonjs_files": [],
            "esm_files": [],
            "mixed_files": [],
            "entry_points": [],
            "circular_dependencies": [],
            "problematic_patterns": [],
            "native_modules": [],
            "dynamic_requires": []
        }
        
        # Scan all JavaScript files
        for js_file in project.rglob("*.js"):
            # Skip node_modules and server directory
            if "node_modules" in str(js_file) or "/server/" in str(js_file):
                continue
            
            analysis["total_files"] += 1
            content = js_file.read_text(encoding='utf-8')
            
            # Check for module system indicators
            has_require = "require(" in content
            has_module_exports = "module.exports" in content or "exports." in content
            has_import = re.search(r"^import\s+", content, re.MULTILINE)
            has_export = re.search(r"^export\s+", content, re.MULTILINE)
            
            # Categorize file
            if (has_require or has_module_exports) and not (has_import or has_export):
                analysis["commonjs_files"].append(str(js_file))
            elif (has_import or has_export) and not (has_require or has_module_exports):
                analysis["esm_files"].append(str(js_file))
            elif has_require or has_module_exports or has_import or has_export:
                analysis["mixed_files"].append(str(js_file))
            
            # Check for problematic patterns
            self._check_problematic_patterns(content, js_file, analysis)
            
            # Check for dynamic requires
            dynamic_requires = re.findall(r"require\([^'\"]+\)", content)
            if dynamic_requires:
                analysis["dynamic_requires"].append({
                    "file": str(js_file),
                    "patterns": dynamic_requires
                })
            
            # Check for native module usage
            native_patterns = ["ffi-napi", "ref-napi", "node-gyp", ".node"]
            for pattern in native_patterns:
                if pattern in content:
                    analysis["native_modules"].append({
                        "file": str(js_file),
                        "pattern": pattern
                    })
        
        # Find entry points
        package_json = project / "package.json"
        if package_json.exists():
            pkg = json.loads(package_json.read_text())
            if "main" in pkg:
                analysis["entry_points"].append(pkg["main"])
            if "bin" in pkg:
                analysis["entry_points"].extend(pkg["bin"].values() if isinstance(pkg["bin"], dict) else [pkg["bin"]])
        
        return analysis
    
    def _apply_hybrid_strategy(self, project: Path, analysis: Dict, order: List) -> Dict:
        """Apply hybrid CommonJS/ESM strategy"""
        
        result = {
            "migrated_files": [],
            "wrapper_files": [],
            "unchanged_files": [],
            "errors": []
        }
        
        # Create dual-mode package configuration
        package_config = self._create_dual_package_config(project)
        
        for file_path in order:
            try:
                file = Path(file_path)
                content = file.read_text(encoding='utf-8')
                
                # Check if file can be safely migrated
                if self._can_safely_migrate(file_path, analysis):
                    # Migrate to ESM
                    migrated_content = self._migrate_to_esm(content)
                    
                    # Save as .mjs for ESM version
                    esm_file = file.with_suffix('.mjs')
                    esm_file.write_text(migrated_content)
                    
                    # Create CommonJS wrapper for compatibility
                    wrapper = self._create_cjs_wrapper(file_path, esm_file)
                    file.write_text(wrapper)
                    
                    result["migrated_files"].append(str(esm_file))
                    result["wrapper_files"].append(str(file))
                else:
                    # Keep as CommonJS but add compatibility layer
                    compat_content = self._add_esm_compatibility(content)
                    file.write_text(compat_content)
                    result["unchanged_files"].append(str(file))
                    
            except Exception as e:
                result["errors"].append({
                    "file": file_path,
                    "error": str(e)
                })
        
        # Update package.json with dual mode support
        self._update_package_json_hybrid(project, package_config)
        
        return result
    
    def _migrate_to_esm(self, content: str) -> str:
        """Convert CommonJS to ESM syntax"""
        
        migrated = content
        
        # Convert require statements to import
        # Handle different require patterns
        patterns = [
            # const x = require('y')
            (r"const\s+(\w+)\s*=\s*require\(['\"]([^'\"]+)['\"]\);?", r"import \1 from '\2';"),
            # const { x, y } = require('z')
            (r"const\s*\{([^}]+)\}\s*=\s*require\(['\"]([^'\"]+)['\"]\);?", r"import { \1 } from '\2';"),
            # require('x')
            (r"require\(['\"]([^'\"]+)['\"]\);?", r"import '\1';"),
        ]
        
        for pattern, replacement in patterns:
            migrated = re.sub(pattern, replacement, migrated)
        
        # Convert module.exports to export
        migrated = re.sub(r"module\.exports\s*=\s*{", "export {", migrated)
        migrated = re.sub(r"module\.exports\s*=\s*(\w+);?", r"export default \1;", migrated)
        migrated = re.sub(r"exports\.(\w+)\s*=\s*", r"export const \1 = ", migrated)
        
        # Handle __dirname and __filename
        if "__dirname" in migrated or "__filename" in migrated:
            esm_shim = """import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

"""
            migrated = esm_shim + migrated
        
        # Convert dynamic imports
        migrated = re.sub(
            r"require\(([^)]+)\)",
            r"await import(\1)",
            migrated
        )
        
        return migrated
    
    def _create_cjs_wrapper(self, original_path: str, esm_path: Path) -> str:
        """Create CommonJS wrapper for ESM module"""
        
        wrapper = f"""// CommonJS wrapper for ESM module
// Auto-generated - Do not edit

const {{ createRequire }} = require('module');
const require = createRequire(import.meta.url);

// Dynamic import of ESM module
module.exports = (async () => {{
    const esmModule = await import('./{esm_path.name}');
    return esmModule.default || esmModule;
}})();

// Synchronous fallback for legacy code
module.exports.__syncFallback = function() {{
    console.warn('Synchronous require of ESM module - consider updating to async');
    // Return a proxy that will load the module on first access
    return new Proxy({{}}, {{
        get(target, prop) {{
            console.error('Accessing ESM module synchronously - this may fail');
            return undefined;
        }}
    }});
}};
"""
        return wrapper
    
    def _add_esm_compatibility(self, content: str) -> str:
        """Add ESM compatibility to CommonJS files"""
        
        compat_header = """// ESM compatibility layer
'use strict';

// Support for import() in CommonJS
if (typeof globalThis.__import === 'undefined') {
    globalThis.__import = (id) => {
        try {
            return Promise.resolve(require(id));
        } catch (err) {
            return import(id);
        }
    };
}

"""
        
        # Add dynamic import support
        content = re.sub(
            r"import\(([^)]+)\)",
            r"globalThis.__import(\1)",
            content
        )
        
        return compat_header + content
    
    def _create_dual_package_config(self, project: Path) -> Dict:
        """Create configuration for dual CommonJS/ESM package"""
        
        config = {
            "type": "commonjs",  # Default to CommonJS for compatibility
            "exports": {
                ".": {
                    "import": "./dist/esm/index.mjs",
                    "require": "./dist/cjs/index.js",
                    "default": "./dist/cjs/index.js"
                }
            },
            "scripts": {
                "build:cjs": "tsc --module commonjs --outDir dist/cjs",
                "build:esm": "tsc --module es2022 --outDir dist/esm && renamer --find .js --replace .mjs 'dist/esm/**/*.js'",
                "build": "npm run build:cjs && npm run build:esm",
                "dev:start": "node --experimental-modules --experimental-specifier-resolution=node ./src/index.js"
            }
        }
        
        return config
    
    def _update_package_json_hybrid(self, project: Path, config: Dict) -> None:
        """Update package.json for hybrid mode"""
        
        package_json = project / "package.json"
        if package_json.exists():
            pkg = json.loads(package_json.read_text())
            
            # Merge configurations
            pkg.update(config)
            
            # Add necessary dev dependencies
            if "devDependencies" not in pkg:
                pkg["devDependencies"] = {}
            
            pkg["devDependencies"].update({
                "renamer": "^4.0.0",
                "@types/node": "^20.0.0",
                "typescript": "^5.0.0"
            })
            
            # Write updated package.json
            package_json.write_text(json.dumps(pkg, indent=2))
    
    def _check_problematic_patterns(self, content: str, file: Path, analysis: Dict) -> None:
        """Check for patterns that complicate ESM migration"""
        
        problems = []
        
        # Check for circular dependencies
        if "require(" in content:
            # Simple circular dependency detection
            requires = re.findall(r"require\(['\"]([^'\"]+)['\"]\)", content)
            for req in requires:
                if req.startswith('.'):
                    # Relative require that might be circular
                    required_file = (file.parent / req).resolve()
                    if required_file.exists():
                        req_content = required_file.read_text(encoding='utf-8')
                        if str(file.name) in req_content:
                            analysis["circular_dependencies"].append({
                                "file1": str(file),
                                "file2": str(required_file)
                            })
        
        # Check for problematic patterns
        problematic = [
            ("eval_require", r"eval\([^)]*require[^)]*\)"),
            ("conditional_require", r"if\s*\([^)]+\)\s*{[^}]*require\("),
            ("try_require", r"try\s*{[^}]*require\("),
            ("computed_require", r"require\([^'\"]+\)"),  # Dynamic requires
            ("global_assignment", r"global\.\w+\s*="),
            ("this_exports", r"this\.exports\s*="),
        ]
        
        for name, pattern in problematic:
            if re.search(pattern, content):
                problems.append(name)
        
        if problems:
            analysis["problematic_patterns"].append({
                "file": str(file),
                "patterns": problems
            })
    
    def _can_safely_migrate(self, file_path: str, analysis: Dict) -> bool:
        """Determine if a file can be safely migrated to ESM"""
        
        # Don't migrate if file has problematic patterns
        for item in analysis["problematic_patterns"]:
            if item["file"] == file_path:
                return False
        
        # Don't migrate if file is part of circular dependency
        for item in analysis["circular_dependencies"]:
            if file_path in [item["file1"], item["file2"]]:
                return False
        
        # Don't migrate if file has dynamic requires
        for item in analysis["dynamic_requires"]:
            if item["file"] == file_path:
                return False
        
        # Don't migrate native module files
        for item in analysis["native_modules"]:
            if item["file"] == file_path:
                return False
        
        return True
    
    def _determine_migration_order(self, analysis: Dict) -> List[str]:
        """Determine safe migration order based on dependencies"""
        
        # Start with leaf modules (no dependencies)
        # Then move up the dependency tree
        all_files = (analysis["commonjs_files"] + 
                    analysis["esm_files"] + 
                    analysis["mixed_files"])
        
        # For now, return files in order found
        # A full implementation would build a dependency graph
        return all_files
    
    def _generate_compatibility_shims(self, analysis: Dict) -> Dict[str, str]:
        """Generate compatibility shims for smooth migration"""
        
        shims = {}
        
        # Shim for require in ESM context
        shims["require_shim.mjs"] = """
// Shim to provide require() in ESM modules
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);

export { require, __filename, __dirname };
"""
        
        # Shim for import in CommonJS context
        shims["import_shim.js"] = """
// Shim to provide import() in CommonJS modules
module.exports.dynamicImport = async function(specifier) {
    if (specifier.endsWith('.mjs')) {
        return await import(specifier);
    }
    
    try {
        // Try require first for CommonJS modules
        return require(specifier);
    } catch (err) {
        // Fall back to dynamic import for ESM modules
        return await import(specifier);
    }
};
"""
        
        # Loader hook for custom resolution
        shims["loader.mjs"] = """
// Custom loader for hybrid CommonJS/ESM resolution
export async function resolve(specifier, context, defaultResolve) {
    // Add custom resolution logic here
    return defaultResolve(specifier, context, defaultResolve);
}

export async function load(url, context, defaultLoad) {
    // Add custom loading logic here
    return defaultLoad(url, context, defaultLoad);
}
"""
        
        return shims
    
    def _create_migration_report(self, result: Dict, analysis: Dict) -> Dict:
        """Create detailed migration report"""
        
        report = {
            "summary": {
                "total_files": analysis["total_files"],
                "migrated": len(result.get("migrated_files", [])),
                "wrapped": len(result.get("wrapper_files", [])),
                "unchanged": len(result.get("unchanged_files", [])),
                "errors": len(result.get("errors", []))
            },
            "risk_assessment": self._assess_migration_risk(analysis),
            "recommendations": self._get_recommendations(analysis, result),
            "breaking_changes": self._identify_breaking_changes(analysis, result)
        }
        
        return report
    
    def _assess_migration_risk(self, analysis: Dict) -> str:
        """Assess overall migration risk"""
        
        risk_score = 0
        
        risk_score += len(analysis["circular_dependencies"]) * 3
        risk_score += len(analysis["problematic_patterns"]) * 2
        risk_score += len(analysis["dynamic_requires"]) * 2
        risk_score += len(analysis["native_modules"]) * 3
        risk_score += len(analysis["mixed_files"]) * 1
        
        if risk_score > 20:
            return "high"
        elif risk_score > 10:
            return "medium"
        return "low"
    
    def _get_recommendations(self, analysis: Dict, result: Dict) -> List[str]:
        """Get specific recommendations for the migration"""
        
        recommendations = []
        
        if analysis["circular_dependencies"]:
            recommendations.append("Refactor circular dependencies before full migration")
        
        if analysis["dynamic_requires"]:
            recommendations.append("Replace dynamic requires with static imports or async imports")
        
        if analysis["native_modules"]:
            recommendations.append("Update native modules to support Node.js 20 and ESM")
        
        if result.get("errors"):
            recommendations.append("Review and fix migration errors before proceeding")
        
        recommendations.append("Test thoroughly in development environment with --experimental-modules flag")
        recommendations.append("Consider using TypeScript for better type safety during migration")
        
        return recommendations
    
    def _identify_breaking_changes(self, analysis: Dict, result: Dict) -> List[str]:
        """Identify potential breaking changes"""
        
        breaking_changes = []
        
        if analysis["native_modules"]:
            breaking_changes.append("Native modules may require recompilation")
        
        if analysis["dynamic_requires"]:
            breaking_changes.append("Dynamic requires converted to async imports - may affect synchronous code flow")
        
        breaking_changes.append("__dirname and __filename require special handling in ESM")
        breaking_changes.append("JSON imports require explicit assert { type: 'json' }")
        
        return breaking_changes
    
    def _get_next_steps(self, result: Dict) -> List[str]:
        """Get next steps after migration"""
        
        return [
            "Run comprehensive test suite",
            "Update CI/CD pipeline for Node.js 20",
            "Test native module compilation on all target platforms",
            "Update documentation with new import/export syntax",
            "Monitor for runtime issues in development environment",
            "Plan staged rollout to production"
        ]
    
    def _apply_gradual_strategy(self, project: Path, analysis: Dict, order: List) -> Dict:
        """Apply gradual migration strategy"""
        # Implementation similar to hybrid but more conservative
        return self._apply_hybrid_strategy(project, analysis, order)
    
    def _apply_full_migration(self, project: Path, analysis: Dict, order: List) -> Dict:
        """Apply full ESM migration"""
        # Implementation for complete migration to ESM
        result = {"migrated_files": [], "errors": []}
        
        for file_path in analysis["commonjs_files"]:
            try:
                file = Path(file_path)
                content = file.read_text(encoding='utf-8')
                migrated = self._migrate_to_esm(content)
                file.write_text(migrated)
                result["migrated_files"].append(str(file))
            except Exception as e:
                result["errors"].append({"file": file_path, "error": str(e)})
        
        return result