from __future__ import annotations

from ast_nodes import Program
from ast_nodes import (
    Assignment,
    BinaryExpr,
    BinaryOperator,
    Block,
    BoolLiteral,
    CallExpr,
    CallStmt,
    Expr,
    FunctionDecl,
    IdentifierExpr,
    IfStmt,
    IntLiteral,
    PrintStmt,
    ReturnStmt,
    Stmt,
    TypeName,
    UnaryExpr,
    UnaryOperator,
    VarDecl,
    WhileStmt,
)
from semantic_errors import SemanticDiagnostic, SemanticError, SemanticErrorKind
from symbols import FunctionSymbol

MAX_INT = (1 << 63) - 1

ARITHMETIC_OPS = {
    BinaryOperator.ADD,
    BinaryOperator.SUBTRACT,
    BinaryOperator.MULTIPLY,
    BinaryOperator.DIVIDE,
    BinaryOperator.REMAINDER,
}

RELATIONAL_OPS = {
    BinaryOperator.LESS,
    BinaryOperator.LESS_EQUAL,
    BinaryOperator.GREATER,
    BinaryOperator.GREATER_EQUAL,
}

EQUALITY_OPS = {
    BinaryOperator.EQUAL,
    BinaryOperator.NOT_EQUAL,
}

LOGICAL_OPS = {
    BinaryOperator.LOGICAL_AND,
    BinaryOperator.LOGICAL_OR,
}


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""

    # 1. Use os símbolos anexados pela resolução de nomes.
    # 2. Determine cada expressão de baixo para cima.
    # 3. Valide operadores, chamadas, comandos e declarações.
    # 4. Anote expressões válidas e acumule os diagnósticos da passagem.
    diagnostics: list[SemanticDiagnostic] = []
    current_function: FunctionDecl | None = None

    def type_of_expr(expr: Expr, in_value_context: bool = True) -> TypeName | None:
        if isinstance(expr, IntLiteral):
            if expr.value < 0 or expr.value > MAX_INT:
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.INTEGER_LITERAL_OUT_OF_RANGE,
                        message=f"Literal inteiro '{expr.value}' fora do intervalo [0, {MAX_INT}]",
                        span=expr.span,
                    )
                )
                return None
            expr.metadata["type"] = TypeName.INT
            return TypeName.INT

        if isinstance(expr, BoolLiteral):
            expr.metadata["type"] = TypeName.BOOL
            return TypeName.BOOL

        if isinstance(expr, IdentifierExpr):
            symbol = expr.metadata.get("symbol")
            if symbol is not None and symbol.type != TypeName.VOID:
                expr.metadata["type"] = symbol.type
                return symbol.type
            return None

        if isinstance(expr, UnaryExpr):
            operand_type = type_of_expr(expr.operand, in_value_context=True)
            if operand_type is None:
                return None

            if expr.operator == UnaryOperator.NEGATE:
                if operand_type != TypeName.INT:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_UNARY_OPERAND,
                            message=f"Operador '-' unário exige 'int', recebeu '{operand_type.value}'",
                            span=expr.span,
                        )
                    )
                    return None
                expr.metadata["type"] = TypeName.INT
                return TypeName.INT

            if expr.operator == UnaryOperator.NOT:
                if operand_type != TypeName.BOOL:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.INVALID_UNARY_OPERAND,
                            message=f"Operador '!' exige 'bool', recebeu '{operand_type.value}'",
                            span=expr.span,
                        )
                    )
                    return None
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL

            return None

        if isinstance(expr, BinaryExpr):
            left_type = type_of_expr(expr.left, in_value_context=True)
            right_type = type_of_expr(expr.right, in_value_context=True)

            if left_type is None or right_type is None:
                return None

            op = expr.operator
            if op in ARITHMETIC_OPS:
                if left_type == TypeName.INT and right_type == TypeName.INT:
                    expr.metadata["type"] = TypeName.INT
                    return TypeName.INT
            elif op in RELATIONAL_OPS:
                if left_type == TypeName.INT and right_type == TypeName.INT:
                    expr.metadata["type"] = TypeName.BOOL
                    return TypeName.BOOL
            elif op in EQUALITY_OPS:
                if (left_type == TypeName.INT and right_type == TypeName.INT) or (
                    left_type == TypeName.BOOL and right_type == TypeName.BOOL
                ):
                    expr.metadata["type"] = TypeName.BOOL
                    return TypeName.BOOL
            elif op in LOGICAL_OPS:
                if left_type == TypeName.BOOL and right_type == TypeName.BOOL:
                    expr.metadata["type"] = TypeName.BOOL
                    return TypeName.BOOL

            diagnostics.append(
                SemanticDiagnostic(
                    kind=SemanticErrorKind.INVALID_BINARY_OPERANDS,
                    message=(
                        f"Operador '{op.value}' não suporta operandos "
                        f"'{left_type.value}' e '{right_type.value}'"
                    ),
                    span=expr.span,
                )
            )
            return None

        if isinstance(expr, CallExpr):
            symbol = expr.metadata.get("symbol")
            if not isinstance(symbol, FunctionSymbol):
                for arg in expr.arguments:
                    type_of_expr(arg, in_value_context=True)
                return None

            expected_params = symbol.parameter_types
            if len(expr.arguments) != len(expected_params):
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.ARITY_MISMATCH,
                        message=(
                            f"Chamada de '{expr.name}' espera {len(expected_params)} "
                            f"argumentos, recebeu {len(expr.arguments)}"
                        ),
                        span=expr.span,
                    )
                )

            arg_types: list[TypeName | None] = []
            for arg in expr.arguments:
                arg_types.append(type_of_expr(arg, in_value_context=True))

            common_len = min(len(expr.arguments), len(expected_params))
            for i in range(common_len):
                arg_type = arg_types[i]
                expected_type = expected_params[i]
                if arg_type is not None and arg_type != expected_type:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                            message=(
                                f"Argumento {i + 1} de '{expr.name}' espera tipo "
                                f"'{expected_type.value}', recebeu '{arg_type.value}'"
                            ),
                            span=expr.arguments[i].span,
                        )
                    )

            if symbol.type == TypeName.VOID:
                if in_value_context:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.VOID_VALUE_USED,
                            message=f"Função 'void' '{expr.name}' usada como valor",
                            span=expr.span,
                        )
                    )
                    return None
                expr.metadata["type"] = TypeName.VOID
                return TypeName.VOID

            expr.metadata["type"] = symbol.type
            return symbol.type

        return None

    def check_stmt(stmt: Stmt) -> None:
        if isinstance(stmt, Block):
            for s in stmt.statements:
                check_stmt(s)

        elif isinstance(stmt, VarDecl):
            if stmt.type == TypeName.VOID:
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.VOID_VARIABLE,
                        message=f"Variável '{stmt.name}' não pode ser do tipo 'void'",
                        span=stmt.span,
                    )
                )
            if stmt.initializer is not None:
                init_type = type_of_expr(stmt.initializer, in_value_context=True)
                if stmt.type != TypeName.VOID and init_type is not None:
                    if init_type != stmt.type:
                        diagnostics.append(
                            SemanticDiagnostic(
                                kind=SemanticErrorKind.INITIALIZER_TYPE_MISMATCH,
                                message=(
                                    f"Inicializador da variável '{stmt.name}' tem tipo "
                                    f"'{init_type.value}', esperado '{stmt.type.value}'"
                                ),
                                span=stmt.initializer.span,
                            )
                        )

        elif isinstance(stmt, Assignment):
            target_type = type_of_expr(stmt.target, in_value_context=True)
            val_type = type_of_expr(stmt.value, in_value_context=True)
            if target_type is not None and val_type is not None:
                if val_type != target_type:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.ASSIGNMENT_TYPE_MISMATCH,
                            message=(
                                f"Atribuição incompatível: variável de tipo "
                                f"'{target_type.value}' recebeu valor de tipo '{val_type.value}'"
                            ),
                            span=stmt.value.span,
                        )
                    )

        elif isinstance(stmt, CallStmt):
            type_of_expr(stmt.call, in_value_context=False)

        elif isinstance(stmt, IfStmt):
            cond_type = type_of_expr(stmt.condition, in_value_context=True)
            if cond_type is not None and cond_type != TypeName.BOOL:
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                        message=f"Condição de 'if' exige tipo 'bool', recebeu '{cond_type.value}'",
                        span=stmt.condition.span,
                    )
                )
            check_stmt(stmt.then_block)
            if stmt.else_block is not None:
                check_stmt(stmt.else_block)

        elif isinstance(stmt, WhileStmt):
            cond_type = type_of_expr(stmt.condition, in_value_context=True)
            if cond_type is not None and cond_type != TypeName.BOOL:
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                        message=f"Condição de 'while' exige tipo 'bool', recebeu '{cond_type.value}'",
                        span=stmt.condition.span,
                    )
                )
            check_stmt(stmt.body)

        elif isinstance(stmt, ReturnStmt):
            expected_type = (
                current_function.return_type if current_function is not None else None
            )
            if stmt.value is None:
                if expected_type != TypeName.VOID:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.RETURN_MISMATCH,
                            message="Comando 'return' sem valor em função não-void",
                            span=stmt.span,
                        )
                    )
            else:
                val_type = type_of_expr(
                    stmt.value, in_value_context=expected_type != TypeName.VOID
                )
                if expected_type == TypeName.VOID:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.RETURN_MISMATCH,
                            message="Função 'void' não pode retornar valor",
                            span=stmt.value.span,
                        )
                    )
                elif val_type is not None and val_type != expected_type:
                    diagnostics.append(
                        SemanticDiagnostic(
                            kind=SemanticErrorKind.RETURN_MISMATCH,
                            message=(
                                f"Tipo de retorno incompatível: esperado '{expected_type.value}', "
                                f"recebeu '{val_type.value}'"
                            ),
                            span=stmt.value.span,
                        )
                    )

        elif isinstance(stmt, PrintStmt):
            for item in stmt.items:
                if isinstance(item, Expr):
                    type_of_expr(item, in_value_context=True)

    for function in program.functions:
        current_function = function
        for param in function.parameters:
            if param.type == TypeName.VOID:
                diagnostics.append(
                    SemanticDiagnostic(
                        kind=SemanticErrorKind.VOID_PARAMETER,
                        message=f"Parâmetro '{param.name}' não pode ser do tipo 'void'",
                        span=param.span,
                    )
                )

        check_stmt(function.body)

    if diagnostics:
        raise SemanticError(diagnostics)
