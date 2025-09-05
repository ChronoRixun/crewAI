# tools/custom_tool.py
"""
Custom tools for Achievement Watcher Node.js modernization
"""

import os
import re
import json
import ast
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class NodeCodeAnalyzerInput(BaseModel):
    """Input schema for NodeCodeAnalyzer"""
    directory_path: str = Field(..., description="Path to the directory to analyze")
    exclude_patterns: List[str] = Field(default=["/server/", "node_modules"], description="Patterns to exclude")

class NodeCodeAnalyzer(BaseTool):
    """Analyzes Node.js code for deprecated patterns and modernization opportunities"""
    name: str = "Node Code Analyzer"
    description: str = "Analyzes Node.js codebase for legacy patterns and modernization opportunities"
    args_schema: type[BaseModel] = NodeCodeAnalyzerInput
    
    def _run(self, directory_path: str, exclude_patterns: List[str] = None) -> Dict:
        """Analyze Node.js code for modernization opportunities"""
        
        if exclude_patterns is None:
            exclude_patterns = ["/server/", "node_modules"]
        
        results = {
            "deprecated_apis": [],
            "callback_patterns": [],
            "var_declarations": [],
            "commonjs_modules": [],
            "legacy_patterns": [],
            "total_files": 0,
            "analysis_summary": {}
        }
        
        # Node.js 14 deprecated APIs that need updating
        deprecated_apis = {
            "fs.exists": "fs.access or fs.stat",
            "fs.existsSync": "fs.accessSync or fs.statSync",
            "crypto.createCredentials": "tls.createSecureContext",
            "crypto.Credentials": "tls.SecureContext",
            "domain": "async/await with try-catch",
            "sys": "util",
            "_writableState": "Use public APIs",
            "_readableState": "Use public APIs",
            "Buffer()": "Buffer.alloc() or Buffer.from()",
            "new Buffer": "Buffer.alloc() or Buffer.from()",
            "process.binding": "Use public APIs",
            "require.extensions": "Use transform hooks"
        }
        
        path = Path(directory_path)
        
        # Analyze all JavaScript files
        for js_file in path.rglob("*.js"):
            # Check exclusion patterns
            if any(pattern in str(js_file) for pattern in exclude_patterns):
                continue
            
            results["total_files"] += 1
            
            try:
                content = js_file.read_text(encoding='utf-8')
                
                # Check for deprecated APIs
                for api, replacement in deprecated_apis.items():
                    if api in content:
                        results["deprecated_apis"].append({
                            "file": str(js_file),
                            "api": api,
                            "replacement": replacement,
                            "line": self._find_line_number(content, api)
                        })
                
                # Check for callback patterns
                callback_patterns = re.findall(r'function\s*\([^)]*callback[^)]*\)', content)
                if callback_patterns:
                    results["callback_patterns"].append({
                        "file": str(js_file),
                        "count": len(callback_patterns),
                        "patterns": callback_patterns[:5]  # First 5 examples
                    })
                
                # Check for var declarations
                var_count = len(re.findall(r'\bvar\s+', content))
                if var_count > 0:
                    results["var_declarations"].append({
                        "file": str(js_file),
                        "count": var_count
                    })
                
                # Check for CommonJS patterns
                if "module.exports" in content or "require(" in content:
                    results["commonjs_modules"].append(str(js_file))
                
                # Check for other legacy patterns
                legacy_checks = [
                    ("arguments.callee", "Use named function expressions"),
                    ("with(", "Avoid with statements"),
                    ("eval(", "Avoid eval for security"),
                    ("== null", "Use === for strict equality"),
                    ("!= null", "Use !== for strict inequality")
                ]
                
                for pattern, recommendation in legacy_checks:
                    if pattern in content:
                        results["legacy_patterns"].append({
                            "file": str(js_file),
                            "pattern": pattern,
                            "recommendation": recommendation
                        })
                
            except Exception as e:
                results["errors"] = results.get("errors", [])
                results["errors"].append({
                    "file": str(js_file),
                    "error": str(e)
                })
        
        # Generate analysis summary
        results["analysis_summary"] = {
            "total_files_analyzed": results["total_files"],
            "files_with_deprecated_apis": len(set(item["file"] for item in results["deprecated_apis"])),
            "files_with_callbacks": len(results["callback_patterns"]),
            "files_with_var": len(results["var_declarations"]),
            "commonjs_files": len(results["commonjs_modules"]),
            "modernization_score": self._calculate_modernization_score(results)
        }
        
        return results
    
    def _find_line_number(self, content: str, pattern: str) -> int:
        """Find the line number where a pattern appears"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if pattern in line:
                return i
        return 0
    
    def _calculate_modernization_score(self, results: Dict) -> int:
        """Calculate a modernization score (0-100)"""
        if results["total_files"] == 0:
            return 100
        
        issues = (
            len(results["deprecated_apis"]) * 3 +
            len(results["callback_patterns"]) * 2 +
            len(results["var_declarations"]) +
            len(results["legacy_patterns"]) * 2
        )
        
        # Normalize to 0-100 scale
        score = max(0, 100 - (issues * 2))
        return score


class DependencyAnalyzerInput(BaseModel):
    """Input schema for DependencyAnalyzer"""
    package_json_path: str = Field(..., description="Path to package.json file")
    check_security: bool = Field(default=True, description="Run security audit")

class DependencyAnalyzer(BaseTool):
    """Analyzes npm dependencies for compatibility and security"""
    name: str = "Dependency Analyzer"
    description: str = "Analyzes npm dependencies for Node.js 20 compatibility and security issues"
    args_schema: type[BaseModel] = DependencyAnalyzerInput
    
    def _run(self, package_json_path: str, check_security: bool = True) -> Dict:
        """Analyze npm dependencies"""
        
        results = {
            "dependencies": {},
            "devDependencies": {},
            "compatibility_issues": [],
            "security_vulnerabilities": [],
            "update_recommendations": [],
            "native_modules": []
        }
        
        package_path = Path(package_json_path)
        
        if not package_path.exists():
            return {"error": f"package.json not found at {package_json_path}"}
        
        # Read package.json
        with open(package_path, 'r') as f:
            package_data = json.load(f)
        
        # Packages known to have issues with Node.js 20
        problematic_packages = {
            "ffi-napi": {
                "issue": "Not compatible with Node.js 20",
                "alternative": "koffi or Node-API",
                "migration_complexity": "high"
            },
            "ref-napi": {
                "issue": "Deprecated, compatibility issues",
                "alternative": "Built into koffi",
                "migration_complexity": "medium"
            },
            "node-sass": {
                "issue": "Native bindings issues",
                "alternative": "sass (Dart Sass)",
                "migration_complexity": "low"
            },
            "fibers": {
                "issue": "Not supported in Node.js 16+",
                "alternative": "async/await",
                "migration_complexity": "high"
            }
        }
        
        # Check dependencies
        all_deps = {
            **package_data.get("dependencies", {}),
            **package_data.get("devDependencies", {})
        }
        
        for dep_name, version in all_deps.items():
            # Check if it's a known problematic package
            if dep_name in problematic_packages:
                results["compatibility_issues"].append({
                    "package": dep_name,
                    "current_version": version,
                    **problematic_packages[dep_name]
                })
            
            # Check if it's a native module
            if any(keyword in dep_name for keyword in ["node-", "-native", "binding", "gyp"]):
                results["native_modules"].append({
                    "package": dep_name,
                    "version": version,
                    "rebuild_required": True
                })
        
        # Run npm outdated to check for updates
        try:
            outdated_output = subprocess.run(
                ["npm", "outdated", "--json"],
                capture_output=True,
                text=True,
                cwd=package_path.parent
            )
            
            if outdated_output.stdout:
                outdated_data = json.loads(outdated_output.stdout)
                for pkg, info in outdated_data.items():
                    results["update_recommendations"].append({
                        "package": pkg,
                        "current": info.get("current"),
                        "wanted": info.get("wanted"),
                        "latest": info.get("latest"),
                        "type": info.get("type")
                    })
        except Exception as e:
            results["errors"] = [f"Failed to check outdated packages: {str(e)}"]
        
        # Run security audit if requested
        if check_security:
            try:
                audit_output = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=package_path.parent
                )
                
                if audit_output.stdout:
                    audit_data = json.loads(audit_output.stdout)
                    if "vulnerabilities" in audit_data:
                        for severity, count in audit_data["vulnerabilities"].items():
                            if count > 0:
                                results["security_vulnerabilities"].append({
                                    "severity": severity,
                                    "count": count
                                })
            except Exception as e:
                results["errors"] = results.get("errors", [])
                results["errors"].append(f"Failed to run security audit: {str(e)}")
        
        # Generate summary
        results["summary"] = {
            "total_dependencies": len(all_deps),
            "compatibility_issues_count": len(results["compatibility_issues"]),
            "native_modules_count": len(results["native_modules"]),
            "updates_available": len(results["update_recommendations"]),
            "security_issues": sum(v["count"] for v in results["security_vulnerabilities"])
        }
        
        return results


class WatchdogServiceAnalyzerInput(BaseModel):
    """Input schema for WatchdogServiceAnalyzer"""
    watchdog_path: str = Field(..., description="Path to watchdog service directory")

class WatchdogServiceAnalyzer(BaseTool):
    """Analyzes the critical watchdog service for modernization"""
    name: str = "Watchdog Service Analyzer"
    description: str = "Analyzes the watchdog service for real-time requirements and modernization"
    args_schema: type[BaseModel] = WatchdogServiceAnalyzerInput
    
    def _run(self, watchdog_path: str) -> Dict:
        """Analyze watchdog service"""
        
        results = {
            "architecture": {},
            "real_time_operations": [],
            "file_monitoring": [],
            "websocket_usage": [],
            "performance_metrics": {},
            "modernization_opportunities": []
        }
        
        watchdog_dir = Path(watchdog_path)
        
        if not watchdog_dir.exists():
            return {"error": f"Watchdog directory not found at {watchdog_path}"}
        
        # Analyze all files in watchdog directory
        for file in watchdog_dir.rglob("*.js"):
            try:
                content = file.read_text(encoding='utf-8')
                
                # Check for file monitoring patterns
                file_watch_patterns = [
                    "fs.watch",
                    "fs.watchFile",
                    "chokidar",
                    "FSWatcher",
                    "fileSystemWatcher"
                ]
                
                for pattern in file_watch_patterns:
                    if pattern in content:
                        results["file_monitoring"].append({
                            "file": str(file),
                            "method": pattern,
                            "can_optimize": pattern in ["fs.watchFile", "fs.watch"]
                        })
                
                # Check for WebSocket usage
                ws_patterns = ["WebSocket", "socket.io", "ws.", "io("]
                for pattern in ws_patterns:
                    if pattern in content:
                        results["websocket_usage"].append({
                            "file": str(file),
                            "pattern": pattern
                        })
                
                # Check for real-time operations
                rt_patterns = [
                    ("setInterval", "Periodic operations"),
                    ("setTimeout", "Delayed operations"),
                    ("process.nextTick", "Immediate async"),
                    ("setImmediate", "I/O callbacks")
                ]
                
                for pattern, description in rt_patterns:
                    count = len(re.findall(pattern, content))
                    if count > 0:
                        results["real_time_operations"].append({
                            "file": str(file),
                            "operation": pattern,
                            "description": description,
                            "count": count
                        })
                
                # Check for performance-critical patterns
                if "Buffer" in content:
                    results["performance_metrics"]["buffer_usage"] = True
                if "Stream" in content:
                    results["performance_metrics"]["stream_usage"] = True
                if "cluster" in content:
                    results["performance_metrics"]["clustering"] = True
                if "worker_threads" in content:
                    results["performance_metrics"]["worker_threads"] = True
                
                # Identify modernization opportunities
                if "callback" in content and "async" not in content:
                    results["modernization_opportunities"].append({
                        "file": str(file),
                        "opportunity": "Convert callbacks to async/await",
                        "impact": "high"
                    })
                
                if not results["performance_metrics"].get("worker_threads") and "CPU" in content:
                    results["modernization_opportunities"].append({
                        "file": str(file),
                        "opportunity": "Implement worker threads for CPU-intensive tasks",
                        "impact": "medium"
                    })
                
            except Exception as e:
                results["errors"] = results.get("errors", [])
                results["errors"].append({
                    "file": str(file),
                    "error": str(e)
                })
        
        # Architecture analysis
        results["architecture"] = {
            "uses_file_monitoring": len(results["file_monitoring"]) > 0,
            "uses_websockets": len(results["websocket_usage"]) > 0,
            "has_real_time_ops": len(results["real_time_operations"]) > 0,
            "performance_optimized": results["performance_metrics"].get("worker_threads", False),
            "modernization_priority": "high" if len(results["modernization_opportunities"]) > 3 else "medium"
        }
        
        return results


class SecurityScannerInput(BaseModel):
    """Input schema for SecurityScanner"""
    project_path: str = Field(..., description="Path to project to scan")
    scan_depth: str = Field(default="comprehensive", description="Scan depth: quick or comprehensive")

class SecurityScanner(BaseTool):
    """Scans for security vulnerabilities"""
    name: str = "Security Scanner"
    description: str = "Scans codebase for security vulnerabilities and compliance issues"
    args_schema: type[BaseModel] = SecurityScannerInput
    
    def _run(self, project_path: str, scan_depth: str = "comprehensive") -> Dict:
        """Perform security scan"""
        
        results = {
            "vulnerabilities": [],
            "insecure_patterns": [],
            "credential_exposure": [],
            "electron_security": [],
            "compliance": {}
        }
        
        project_dir = Path(project_path)
        
        # Security patterns to check
        security_patterns = [
            (r"eval\([^)]+\)", "Use of eval - potential code injection", "high"),
            (r"innerHTML\s*=", "Direct innerHTML assignment - XSS risk", "high"),
            (r"document\.write", "document.write usage - XSS risk", "medium"),
            (r"require\([^'\"]+\)", "Dynamic require - potential security risk", "medium"),
            (r"child_process\.exec\(", "exec without validation - command injection risk", "high"),
            (r"fs\..*Sync\(", "Synchronous file operations - DoS risk", "low"),
            (r"crypto\.createCipher\(", "Deprecated cipher - use createCipheriv", "high"),
            (r"Math\.random\(\)", "Weak randomness for security", "medium")
        ]
        
        # Scan for security issues
        for js_file in project_dir.rglob("*.js"):
            if "node_modules" in str(js_file):
                continue
            
            try:
                content = js_file.read_text(encoding='utf-8')
                
                # Check for security patterns
                for pattern, description, severity in security_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        results["insecure_patterns"].append({
                            "file": str(js_file),
                            "pattern": pattern,
                            "description": description,
                            "severity": severity,
                            "occurrences": len(matches)
                        })
                
                # Check for hardcoded credentials
                cred_patterns = [
                    r"['\"]password['\"]\s*[:=]\s*['\"][^'\"]+['\"]",
                    r"['\"]api[_-]?key['\"]\s*[:=]\s*['\"][^'\"]+['\"]",
                    r"['\"]secret['\"]\s*[:=]\s*['\"][^'\"]+['\"]"
                ]
                
                for pattern in cred_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        results["credential_exposure"].append({
                            "file": str(js_file),
                            "type": "Potential hardcoded credential"
                        })
                
                # Electron-specific security checks
                if "electron" in content.lower():
                    electron_issues = []
                    
                    if "nodeIntegration: true" in content:
                        electron_issues.append("nodeIntegration enabled - security risk")
                    if "contextIsolation: false" in content:
                        electron_issues.append("contextIsolation disabled - security risk")
                    if "webSecurity: false" in content:
                        electron_issues.append("webSecurity disabled - security risk")
                    
                    if electron_issues:
                        results["electron_security"].append({
                            "file": str(js_file),
                            "issues": electron_issues
                        })
                
            except Exception as e:
                results["errors"] = results.get("errors", [])
                results["errors"].append({"file": str(js_file), "error": str(e)})
        
        # Generate compliance summary
        results["compliance"] = {
            "total_issues": len(results["insecure_patterns"]) + len(results["credential_exposure"]),
            "high_severity": len([x for x in results["insecure_patterns"] if x["severity"] == "high"]),
            "electron_secure": len(results["electron_security"]) == 0,
            "recommendation": "Address high severity issues immediately"
        }
        
        return results


class TestGeneratorInput(BaseModel):
    """Input schema for TestGenerator"""
    source_file: str = Field(..., description="Source file to generate tests for")
    test_framework: str = Field(default="jest", description="Test framework to use")

class TestGenerator(BaseTool):
    """Generates comprehensive test suites"""
    name: str = "Test Generator"
    description: str = "Generates unit and integration tests for modernized code"
    args_schema: type[BaseModel] = TestGeneratorInput
    
    def _run(self, source_file: str, test_framework: str = "jest") -> Dict:
        """Generate tests for source file"""
        
        results = {
            "test_file": "",
            "test_cases": [],
            "coverage_estimate": 0,
            "test_code": ""
        }
        
        source_path = Path(source_file)
        
        if not source_path.exists():
            return {"error": f"Source file not found: {source_file}"}
        
        # Read source file
        source_content = source_path.read_text(encoding='utf-8')
        
        # Parse functions and classes
        functions = re.findall(r'(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', source_content)
        functions = [f[0] or f[1] for f in functions if f[0] or f[1]]
        
        # Generate test file path
        test_file = source_path.parent / "__tests__" / f"{source_path.stem}.test.js"
        results["test_file"] = str(test_file)
        
        # Generate test template
        test_template = f"""// Test suite for {source_path.name}
// Generated by Node.js Modernization Tool

const {{ {', '.join(functions)} }} = require('../{source_path.stem}');

describe('{source_path.stem}', () => {{
"""
        
        # Generate test cases for each function
        for func in functions:
            test_case = f"""
    describe('{func}', () => {{
        it('should execute without errors', async () => {{
            // Test basic functionality
            expect({func}).toBeDefined();
            expect(typeof {func}).toBe('function');
        }});
        
        it('should handle valid input', async () => {{
            // TODO: Add specific test for valid input
            // const result = await {func}(validInput);
            // expect(result).toBeDefined();
        }});
        
        it('should handle invalid input', async () => {{
            // TODO: Add specific test for invalid input
            // await expect({func}(invalidInput)).rejects.toThrow();
        }});
        
        it('should handle edge cases', async () => {{
            // TODO: Add edge case tests
        }});
    }});
"""
            test_template += test_case
            
            results["test_cases"].append({
                "function": func,
                "tests": ["basic", "valid_input", "invalid_input", "edge_cases"]
            })
        
        test_template += "\n});\n"
        
        results["test_code"] = test_template
        results["coverage_estimate"] = min(len(functions) * 25, 100)  # Rough estimate
        
        return results


class NodeVersionMigratorInput(BaseModel):
    """Input schema for NodeVersionMigrator"""
    source_code: str = Field(..., description="Source code to migrate")
    target_version: str = Field(default="20", description="Target Node.js version")

class NodeVersionMigrator(BaseTool):
    """Migrates code to target Node.js version"""
    name: str = "Node Version Migrator"
    description: str = "Automatically migrates code patterns to target Node.js version"
    args_schema: type[BaseModel] = NodeVersionMigratorInput
    
    def _run(self, source_code: str, target_version: str = "20") -> Dict:
        """Migrate code to target Node.js version"""
        
        migrated_code = source_code
        changes_made = []
        
        # Migration patterns for Node.js 20
        migrations = [
            # Callback to async/await
            {
                "pattern": r"(\w+)\((.*?),\s*function\s*\((err|error),\s*(\w+)\)\s*{",
                "replacement": r"try {\n    const \4 = await \1(\2);",
                "description": "Convert callback to async/await"
            },
            # var to const/let
            {
                "pattern": r"\bvar\s+",
                "replacement": "let ",
                "description": "Replace var with let"
            },
            # Buffer constructor
            {
                "pattern": r"new Buffer\(([^)]+)\)",
                "replacement": r"Buffer.from(\1)",
                "description": "Update Buffer constructor"
            },
            # fs.exists to fs.access
            {
                "pattern": r"fs\.exists\(([^,]+),",
                "replacement": r"fs.access(\1, fs.constants.F_OK,",
                "description": "Replace deprecated fs.exists"
            },
            # String includes instead of indexOf
            {
                "pattern": r"\.indexOf\(([^)]+)\)\s*!==?\s*-1",
                "replacement": r".includes(\1)",
                "description": "Use includes() instead of indexOf()"
            }
        ]
        
        # Apply migrations
        for migration in migrations:
            pattern = migration["pattern"]
            replacement = migration["replacement"]
            
            matches = re.findall(pattern, migrated_code)
            if matches:
                migrated_code = re.sub(pattern, replacement, migrated_code)
                changes_made.append({
                    "type": migration["description"],
                    "occurrences": len(matches)
                })
        
        # Add modern features
        if "fetch(" not in migrated_code and ("axios" in migrated_code or "request" in migrated_code):
            changes_made.append({
                "type": "Consider using native fetch API",
                "recommendation": "Node.js 20 includes native fetch"
            })
        
        return {
            "migrated_code": migrated_code,
            "changes_made": changes_made,
            "migration_summary": {
                "total_changes": sum(c.get("occurrences", 0) for c in changes_made),
                "change_types": len(changes_made)
            }
        }