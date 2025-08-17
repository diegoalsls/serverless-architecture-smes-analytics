# lambda_handler.py  (handler principal de la única Lambda)
import json
import cups
import pacientes
import mensual_proc

def lambda_handler(event, context):
    """Orquesta los tres flujos: CUPS, Pacientes y Consolidador Mensual."""
    
    result = {"cups": None, "pacientes": None, "mensual_proc": None}

    # Ejecutar CUPS
    try:
        result["cups"] = cups.process_cups(event, context)
    except Exception as exc:
        result["cups"] = {"status": "ERROR", "message": str(exc)}

    # Ejecutar Pacientes
    try:
        result["pacientes"] = pacientes.process_pacientes(event, context)
    except Exception as exc:
        result["pacientes"] = {"status": "ERROR", "message": str(exc)}

    # Ejecutar Consolidado Mensual
    try:
        result["mensual_proc"] = mensual_proc.process_mensual_proc(event, context)
    except Exception as exc:
        result["mensual_proc"] = {"status": "ERROR", "message": str(exc)}

    # Registrar en CloudWatch
    print("Orchestrator result:", json.dumps(result, ensure_ascii=False, indent=2))
    return result
