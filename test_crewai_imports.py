#!/usr/bin/env python3
"""
Script de prueba para verificar que todas las importaciones de CrewAI funcionan correctamente.
Útil para debugging de problemas de importación.
"""

import sys
import traceback

def test_import(module_name, description):
    """Prueba la importación de un módulo y reporta el resultado."""
    try:
        if module_name == "crewai.tools.BaseTool":
            from crewai.tools import BaseTool
            print(f"✅ {description}: BaseTool importado correctamente")
        elif module_name == "crewai_tools.SerperDevTool":
            from crewai_tools import SerperDevTool
            print(f"✅ {description}: SerperDevTool importado correctamente")
        elif module_name == "cadastro_crew.tools.supabase":
            from cadastro_crew.tools.supabase_document_tool import SupabaseDocumentContentTool
            print(f"✅ {description}: SupabaseDocumentContentTool importado correctamente")
        elif module_name == "cadastro_crew.tools.knowledge_base":
            from cadastro_crew.tools.knowledge_base_query_tool import KnowledgeBaseQueryTool
            print(f"✅ {description}: KnowledgeBaseQueryTool importado correctamente")
        elif module_name == "cadastro_crew.tools.llama_parse":
            from cadastro_crew.tools.llama_cloud_parsing_tool import LlamaParseDirectTool
            print(f"✅ {description}: LlamaParseDirectTool importado correctamente")
        elif module_name == "cadastro_crew.crew":
            from cadastro_crew.crew import CadastroCrew
            print(f"✅ {description}: CadastroCrew importado correctamente")
        elif module_name == "cadastro_crew.agents":
            from cadastro_crew.agents import CadastroAgents
            print(f"✅ {description}: CadastroAgents importado correctamente")
        else:
            exec(f"import {module_name}")
            print(f"✅ {description}: {module_name} importado correctamente")
        return True
    except Exception as e:
        print(f"❌ {description}: Error al importar {module_name}")
        print(f"   Error: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def main():
    """Ejecuta todas las pruebas de importación."""
    print("🔍 Verificando importaciones de CrewAI y herramientas personalizadas...")
    print("=" * 70)
    
    tests = [
        ("crewai", "CrewAI base"),
        ("crewai.tools.BaseTool", "BaseTool de CrewAI"),
        ("crewai_tools.SerperDevTool", "SerperDevTool"),
        ("cadastro_crew.tools.supabase", "Herramienta Supabase personalizada"),
        ("cadastro_crew.tools.knowledge_base", "Herramienta Knowledge Base personalizada"),
        ("cadastro_crew.tools.llama_parse", "Herramienta LlamaParse personalizada"),
        ("cadastro_crew.agents", "Agentes de Cadastro"),
        ("cadastro_crew.crew", "CadastroCrew"),
    ]
    
    passed = 0
    failed = 0
    
    for module_name, description in tests:
        if test_import(module_name, description):
            passed += 1
        else:
            failed += 1
        print()
    
    print("=" * 70)
    print(f"📊 Resultados: {passed} ✅ exitosas, {failed} ❌ fallidas")
    
    if failed == 0:
        print("🎉 ¡Todas las importaciones funcionan correctamente!")
        
        # Prueba adicional: crear una instancia de CadastroCrew
        try:
            print("\n🧪 Prueba adicional: Creando instancia de CadastroCrew...")
            from cadastro_crew.crew import CadastroCrew
            crew = CadastroCrew(inputs={"case_id": "test", "documents": [], "checklist": "test", "current_date": "2025-01-01"})
            print("✅ Instancia de CadastroCrew creada exitosamente")
        except Exception as e:
            print(f"❌ Error al crear instancia de CadastroCrew: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
    else:
        print("⚠️ Hay problemas de importación que deben resolverse.")
        sys.exit(1)

if __name__ == "__main__":
    main() 