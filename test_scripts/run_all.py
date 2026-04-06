import os
import subprocess
import sys
import time

def run_all_tests():
    # Directorio actual donde esta el script
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Buscar todos los archivos test_*.py excluyendo este mismo script
    test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]
    test_files.sort()

    if not test_files:
        print("No se encontraron scripts de test.")
        return

    print(f"Se encontraron {len(test_files)} archivos de test. Iniciando ejecucion...\n")
    
    passed_tests = []
    failed_tests = []
    
    start_time = time.time()

    for test_file in test_files:
        test_path = os.path.join(test_dir, test_file)
        print("="*50    )
        print(f"EJECUTANDO: {test_file}")
        print("="*50)
        
        # Ejecuta el script como un subproceso
        result = subprocess.run([sys.executable, test_path], capture_output=False)
        
        if result.returncode == 0:
            passed_tests.append(test_file)
            print(f"\n[OK] {test_file} finalizo correctamente.\n")
        else:
            failed_tests.append(test_file)
            print(f"\n[FAIL] {test_file} devolvio error (Codigo {result.returncode}).\n")

    end_time = time.time()
    
    # Resumen Final
    print("="*50)
    print("RESUMEN DE TESTS")
    print("="*50)
    print(f"Tiempo total: {round(end_time - start_time, 2)} segundos")
    print(f"Tests Pasados: {len(passed_tests)}/{len(test_files)}")
    
    if failed_tests:
        print("Tests Fallidos:")
        for f in failed_tests:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("\nTODOS LOS TESTS PASARON CORRECTAMENTE.")
        sys.exit(0)

if __name__ == "__main__":
    run_all_tests()