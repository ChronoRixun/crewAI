# tools/native_module_migrator.py
"""
Enhanced tool for migrating from ffi-napi to modern alternatives
"""

from crewai_tools import BaseTool
from pydantic import BaseModel, Field
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

class NativeModuleMigratorInput(BaseModel):
    file_path: str = Field(..., description="Path to file using ffi-napi")
    target_solution: str = Field(default="koffi", description="Migration target: koffi, node-api, or hybrid")

class NativeModuleMigrator(BaseTool):
    name: str = "Native Module Migrator"
    description: str = "Migrates ffi-napi code to modern alternatives with fallback strategies"
    args_schema: type[BaseModel] = NativeModuleMigratorInput
    
    def _run(self, file_path: str, target_solution: str = "koffi") -> Dict[str, Any]:
        """Migrate native module usage with multiple strategies"""
        
        file = Path(file_path)
        if not file.exists():
            return {"error": f"File not found: {file_path}"}
        
        content = file.read_text(encoding='utf-8')
        
        # Analyze ffi-napi usage patterns
        analysis = self._analyze_ffi_usage(content)
        
        # Generate migration based on target solution
        if target_solution == "koffi":
            migrated = self._migrate_to_koffi(content, analysis)
        elif target_solution == "node-api":
            migrated = self._migrate_to_node_api(content, analysis)
        elif target_solution == "hybrid":
            migrated = self._create_hybrid_solution(content, analysis)
        else:
            return {"error": f"Unknown target solution: {target_solution}"}
        
        # Add compatibility layer
        migrated = self._add_compatibility_layer(migrated, analysis)
        
        # Generate test cases
        tests = self._generate_migration_tests(analysis)
        
        return {
            "status": "success",
            "original_file": file_path,
            "analysis": analysis,
            "migrated_code": migrated,
            "test_cases": tests,
            "compatibility_notes": self._get_compatibility_notes(analysis),
            "fallback_strategy": self._create_fallback_strategy(analysis)
        }
    
    def _analyze_ffi_usage(self, content: str) -> Dict[str, Any]:
        """Deep analysis of ffi-napi usage patterns"""
        
        patterns = {
            "library_loads": re.findall(r"ffi\.Library\(['\"](.+?)['\"]", content),
            "struct_definitions": re.findall(r"ref\.types\.(.*?)[\s,\)]", content),
            "function_bindings": re.findall(r"['\"](.*?)['\"]:\s*\[.*?\]", content),
            "callbacks": re.findall(r"ffi\.Callback\((.*?)\)", content, re.DOTALL),
            "buffer_usage": re.findall(r"ref\.alloc\((.*?)\)", content),
            "pointer_operations": re.findall(r"ref\.(deref|readPointer|writePointer)", content)
        }
        
        # Identify Windows-specific APIs
        windows_apis = {
            "user32": ["ShowWindow", "SetWindowPos", "GetForegroundWindow"],
            "kernel32": ["GetCurrentProcess", "OpenProcess", "ReadProcessMemory"],
            "psapi": ["EnumProcesses", "GetModuleFileNameEx"],
            "advapi32": ["OpenProcessToken", "GetTokenInformation"]
        }
        
        used_apis = {}
        for lib in patterns["library_loads"]:
            lib_name = Path(lib).stem.lower()
            if lib_name in windows_apis:
                used_apis[lib_name] = [api for api in windows_apis[lib_name] 
                                       if api in content]
        
        return {
            "patterns": patterns,
            "windows_apis": used_apis,
            "complexity": self._assess_complexity(patterns),
            "risk_level": self._assess_risk(patterns, used_apis)
        }
    
    def _migrate_to_koffi(self, content: str, analysis: Dict) -> str:
        """Migrate ffi-napi to koffi with proper error handling"""
        
        migrated = content
        
        # Replace imports
        migrated = re.sub(
            r"const ffi = require\(['\"]ffi-napi['\"]\);?",
            "const koffi = require('koffi');",
            migrated
        )
        
        migrated = re.sub(
            r"const ref = require\(['\"]ref-napi['\"]\);?",
            "// ref-napi functionality integrated into koffi",
            migrated
        )
        
        # Migrate Library declarations
        for lib_path in analysis["patterns"]["library_loads"]:
            old_pattern = f"ffi.Library('{lib_path}',"
            new_code = f"""koffi.load('{lib_path}');
// Define functions after loading library"""
            migrated = migrated.replace(old_pattern, new_code)
        
        # Migrate function definitions
        migrated = self._migrate_function_definitions(migrated)
        
        # Migrate struct definitions
        migrated = self._migrate_struct_definitions(migrated, analysis)
        
        # Add error handling wrapper
        error_wrapper = """
// Koffi compatibility wrapper
const koffiWrapper = {
    call: async (func, ...args) => {
        try {
            return await func(...args);
        } catch (error) {
            console.error('Koffi call failed:', error);
            // Fallback to alternative implementation if available
            if (global.fallbackImplementation && global.fallbackImplementation[func.name]) {
                return global.fallbackImplementation[func.name](...args);
            }
            throw error;
        }
    }
};
"""
        migrated = error_wrapper + "\n" + migrated
        
        return migrated
    
    def _migrate_to_node_api(self, content: str, analysis: Dict) -> str:
        """Create Node-API/N-API wrapper for native functionality"""
        
        # Generate C++ binding file
        cpp_binding = self._generate_cpp_binding(analysis)
        
        # Generate JavaScript wrapper
        js_wrapper = f"""
// Node-API wrapper for native functionality
const {{ promisify }} = require('util');
const binding = require('./build/Release/achievement_watcher_native');

// Wrap native functions in promises
const nativeAPI = {{
    {self._generate_js_bindings(analysis)}
}};

module.exports = nativeAPI;
"""
        
        # Update package.json binding.gyp configuration
        gyp_config = self._generate_gyp_config(analysis)
        
        return {
            "js_wrapper": js_wrapper,
            "cpp_binding": cpp_binding,
            "gyp_config": gyp_config
        }
    
    def _create_hybrid_solution(self, content: str, analysis: Dict) -> Dict[str, str]:
        """Create hybrid solution using multiple approaches"""
        
        # For simple Windows API calls, use child_process
        child_process_solution = """
// Hybrid solution using child_process for simple Windows API calls
const { execSync, spawn } = require('child_process');
const path = require('path');

class NativeAPIWrapper {
    constructor() {
        this.useKoffi = false;
        this.useChildProcess = true;
        
        // Try to load koffi, fallback to child_process
        try {
            this.koffi = require('koffi');
            this.useKoffi = true;
        } catch (error) {
            console.log('Koffi not available, using child_process fallback');
        }
    }
    
    async callWindowsAPI(dll, func, args) {
        if (this.useKoffi) {
            return this._callViaKoffi(dll, func, args);
        } else {
            return this._callViaChildProcess(dll, func, args);
        }
    }
    
    _callViaChildProcess(dll, func, args) {
        // PowerShell wrapper for Windows API calls
        const psCommand = `
            Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Win32 {
                    [DllImport("${dll}.dll")]
                    public static extern ${this._generatePInvokeSignature(func, args)};
                }
            "@
            [Win32]::${func}(${args.join(',')})
        `;
        
        try {
            const result = execSync(`powershell -Command "${psCommand}"`, {
                encoding: 'utf8',
                windowsHide: true
            });
            return result.trim();
        } catch (error) {
            console.error(`Failed to call ${dll}.${func}:`, error);
            throw error;
        }
    }
}
"""
        
        # For complex operations, provide pure JS alternatives
        pure_js_alternatives = self._generate_pure_js_alternatives(analysis)
        
        return {
            "hybrid_wrapper": child_process_solution,
            "pure_js_alternatives": pure_js_alternatives,
            "migration_notes": self._generate_migration_notes(analysis)
        }
    
    def _add_compatibility_layer(self, code: str, analysis: Dict) -> str:
        """Add compatibility layer for gradual migration"""
        
        compatibility_layer = """
// Compatibility layer for gradual migration
const compatibilityLayer = {
    isLegacyMode: process.env.USE_LEGACY_FFI === 'true',
    
    async loadLibrary(name, functions) {
        if (this.isLegacyMode) {
            // Use old ffi-napi if in legacy mode
            const ffi = require('ffi-napi');
            return ffi.Library(name, functions);
        } else {
            // Use new implementation
            return this.loadModernLibrary(name, functions);
        }
    },
    
    loadModernLibrary(name, functions) {
        // Modern implementation
        const lib = require('koffi').load(name);
        const wrappedFunctions = {};
        
        for (const [funcName, signature] of Object.entries(functions)) {
            wrappedFunctions[funcName] = lib.func(funcName, ...signature);
        }
        
        return wrappedFunctions;
    }
};

// Export compatibility layer
module.exports = compatibilityLayer;
"""
        
        return compatibility_layer + "\n\n" + code
    
    def _generate_migration_tests(self, analysis: Dict) -> List[str]:
        """Generate comprehensive test cases for migration validation"""
        
        tests = []
        
        # Test for each Windows API function
        for lib, functions in analysis["windows_apis"].items():
            for func in functions:
                test = f"""
describe('{lib}.{func} migration', () => {{
    it('should maintain compatibility with original behavior', async () => {{
        const original = require('./legacy/{lib}');
        const migrated = require('./migrated/{lib}');
        
        // Test with common parameters
        const testParams = {self._generate_test_params(func)};
        
        const originalResult = await original.{func}(...testParams);
        const migratedResult = await migrated.{func}(...testParams);
        
        expect(migratedResult).toEqual(originalResult);
    }});
    
    it('should handle errors gracefully', async () => {{
        const migrated = require('./migrated/{lib}');
        
        // Test with invalid parameters
        await expect(migrated.{func}(null)).rejects.toThrow();
    }});
}});
"""
                tests.append(test)
        
        return tests
    
    def _assess_complexity(self, patterns: Dict) -> str:
        """Assess migration complexity"""
        score = 0
        score += len(patterns["callbacks"]) * 3  # Callbacks are complex
        score += len(patterns["struct_definitions"]) * 2
        score += len(patterns["pointer_operations"]) * 2
        score += len(patterns["function_bindings"])
        
        if score > 20:
            return "high"
        elif score > 10:
            return "medium"
        return "low"
    
    def _assess_risk(self, patterns: Dict, apis: Dict) -> str:
        """Assess migration risk level"""
        high_risk_apis = ["ReadProcessMemory", "WriteProcessMemory", "OpenProcess"]
        
        for lib, functions in apis.items():
            if any(api in high_risk_apis for api in functions):
                return "high"
        
        if len(patterns["callbacks"]) > 2:
            return "medium"
        
        return "low"
    
    def _generate_test_params(self, func: str) -> str:
        """Generate appropriate test parameters for a function"""
        param_map = {
            "ShowWindow": "[handle, SW_SHOW]",
            "GetForegroundWindow": "[]",
            "OpenProcess": "[PROCESS_ALL_ACCESS, false, pid]",
            "EnumProcesses": "[buffer, size, bytesReturned]"
        }
        return param_map.get(func, "[]")
    
    def _generate_pure_js_alternatives(self, analysis: Dict) -> str:
        """Generate pure JavaScript alternatives where possible"""
        alternatives = """
// Pure JavaScript alternatives for common native operations
const pureJSAlternatives = {
    // Process enumeration without native calls
    async enumProcesses() {
        const { exec } = require('child_process');
        const { promisify } = require('util');
        const execAsync = promisify(exec);
        
        if (process.platform === 'win32') {
            const { stdout } = await execAsync('wmic process get ProcessId,Name,ExecutablePath /FORMAT:CSV');
            return this._parseWmicOutput(stdout);
        }
        // Add Linux/Mac support as needed
    },
    
    // Window manipulation using Electron APIs
    manipulateWindow(action, ...args) {
        const { BrowserWindow } = require('electron');
        const win = BrowserWindow.getFocusedWindow();
        
        if (win) {
            switch(action) {
                case 'show': win.show(); break;
                case 'hide': win.hide(); break;
                case 'minimize': win.minimize(); break;
                case 'maximize': win.maximize(); break;
            }
        }
    },
    
    _parseWmicOutput(output) {
        const lines = output.split('\\n').filter(line => line.trim());
        const processes = [];
        
        for (let i = 2; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length >= 3) {
                processes.push({
                    pid: parseInt(parts[2]),
                    name: parts[1],
                    path: parts[0]
                });
            }
        }
        
        return processes;
    }
};
"""
        return alternatives

    def _migrate_function_definitions(self, content: str) -> str:
        """Convert ffi function definitions to koffi format"""
        # Implementation would go here
        return content
    
    def _migrate_struct_definitions(self, content: str, analysis: Dict) -> str:
        """Convert ref-napi struct definitions to koffi format"""
        # Implementation would go here
        return content
    
    def _generate_cpp_binding(self, analysis: Dict) -> str:
        """Generate C++ binding code for Node-API"""
        # Implementation would go here
        return "// C++ binding code"
    
    def _generate_js_bindings(self, analysis: Dict) -> str:
        """Generate JavaScript bindings for Node-API"""
        # Implementation would go here
        return "// JS bindings"
    
    def _generate_gyp_config(self, analysis: Dict) -> Dict:
        """Generate binding.gyp configuration"""
        # Implementation would go here
        return {"targets": []}
    
    def _get_compatibility_notes(self, analysis: Dict) -> List[str]:
        """Get specific compatibility notes"""
        # Implementation would go here
        return ["Note about compatibility"]
    
    def _create_fallback_strategy(self, analysis: Dict) -> Dict:
        """Create fallback strategy for critical functions"""
        # Implementation would go here
        return {"strategy": "Use child_process for critical functions"}
    
    def _generate_migration_notes(self, analysis: Dict) -> str:
        """Generate detailed migration notes"""
        # Implementation would go here
        return "// Migration notes"
    
    def _generatePInvokeSignature(self, func: str, args: List) -> str:
        """Generate P/Invoke signature for PowerShell"""
        # Implementation would go here
        return f"IntPtr {func}(IntPtr param)"