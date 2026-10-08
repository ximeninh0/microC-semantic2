from __future__ import annotations

from ast_nodes import (
    Assignment,
    BinaryExpr,
    Block,
    BoolLiteral,
    CallExpr,
    CallStmt,
    Expr,
    IdentifierExpr,
    IfStmt,
    IntLiteral,
    Parameter,
    PrintStmt,
    Program,
    ReturnStmt,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)
from semantic_errors import SemanticDiagnostic, SemanticError, SemanticErrorKind
from symbols import FunctionSymbol, SymbolKind, Scope, Symbol


def resolve_names(program: Program) -> None:
    functions: dict[str, FunctionSymbol] = {}
    diagnostics: list[SemanticDiagnostic] = []

    def declare(node: Parameter | VarDecl, kind: SymbolKind, scope: Scope) -> None:
        symbol = Symbol(node.name, kind, node.type, node)
        node.metadata["symbol"] = symbol
        
        if node.name not in scope.symbols: # verificar se a declaração não está duplicada 
            scope.symbols[node.name] = symbol
        else:
            diagnostics.append(SemanticDiagnostic(
                kind=SemanticErrorKind.DUPLICATE_DECLARATION,
                message=f"Declaração '{node.name}' duplicada",
                span=node.span,
            ))

    def lookup(name: str, scope: Scope) -> Symbol | None:
        atual = scope
        while atual is not None:
            if name in atual.symbols:
                return atual.symbols[name]
            atual = atual.parent
        return None  # se não encontrou retorna None                          

    def visit_expr(expr: Expr, scope: Scope) -> None:
        if isinstance(expr, IdentifierExpr):
            symbol = lookup(expr.name, scope)
            if symbol is not None:
                expr.metadata["symbol"] = symbol
            else: # lookup retorna None se não encontrou declaração
                diagnostics.append(SemanticDiagnostic(
                    kind=SemanticErrorKind.UNDECLARED_VARIABLE,
                    message=f"Variável '{expr.name}' não declarada",
                    span=expr.span,
                ))

        elif isinstance(expr, CallExpr):
            if expr.name in functions:
                expr.metadata["symbol"] = functions[expr.name]
            else: # se o nome da funcao não está em functions, ela não foi declarada
                diagnostics.append(SemanticDiagnostic(
                    kind=SemanticErrorKind.UNDECLARED_FUNCTION,
                    message=f"Função '{expr.name}' não declarada",
                    span=expr.span,
                ))
            for argument in expr.arguments:
                visit_expr(argument, scope)

        # expressão com lado esquerdo e direito x + y
        elif isinstance(expr, BinaryExpr):
            visit_expr(expr.left, scope)
            visit_expr(expr.right, scope)

        # expressão unária -x, !y
        elif isinstance(expr, UnaryExpr):
            visit_expr(expr.operand, scope)

        elif isinstance(expr, (IntLiteral, BoolLiteral)):
            pass  # literais não usam nomes

    def visit_stmt(stmt: Stmt, scope: Scope) -> None:

        # bloco { }
        if isinstance(stmt, Block):
            # bloco interno
            inner = Scope(parent=scope) # escopo interno, passado na recursiva
            stmt.metadata["scope"] = inner
            for statement in stmt.statements:
                visit_stmt(statement, inner)

        # scope de todos os outros passados é o pai

        # declaracao de variavel tipo int x = 1;
        elif isinstance(stmt, VarDecl):
            # declara antes do inicializador: em `int y = y;` o uso é o novo y
            declare(stmt, SymbolKind.VARIABLE, scope)
            if stmt.initializer is not None:
                visit_expr(stmt.initializer, scope)

        # atribuicao x = ...
        elif isinstance(stmt, Assignment):
            visit_expr(stmt.target, scope)
            visit_expr(stmt.value, scope)

        # chamada de funcao sozinha como comando f(1);
        elif isinstance(stmt, CallStmt):
            visit_expr(stmt.call, scope)

        # if: confere a condicao e depois os blocos (o else pode nao existir)
        elif isinstance(stmt, IfStmt):
            visit_expr(stmt.condition, scope)
            visit_stmt(stmt.then_block, scope)
            if stmt.else_block is not None:
                visit_stmt(stmt.else_block, scope)

        # while: confere a condicao e o corpo do laco
        elif isinstance(stmt, WhileStmt):
            visit_expr(stmt.condition, scope)
            visit_stmt(stmt.body, scope)

        # return: so tem algo pra olhar se tiver valor (return; nao tem)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                visit_expr(stmt.value, scope)

        # print: passa por cada item, menos as strings
        elif isinstance(stmt, PrintStmt):
            for item in stmt.items:
                if not isinstance(item, StringLiteral):  # strings não têm nomes
                    visit_expr(item, scope)

    # 1. Colete todas as assinaturas de função.
    for function in program.functions:
        function_symbol = FunctionSymbol(
            name=function.name,
            kind=SymbolKind.FUNCTION,
            type=function.return_type,
            declaration=function,
            parameter_types=tuple(p.type for p in function.parameters),
        )
        function.metadata["symbol"] = function_symbol

        if function.name in functions:
            diagnostics.append(SemanticDiagnostic(
                kind=SemanticErrorKind.DUPLICATE_FUNCTION,
                message=f"Função '{function.name}' já declarada",
                span=function.span,
            ))
        else:
            functions[function.name] = function_symbol

    # 2. Valide a existência e a assinatura de main.
    main = functions.get("main")
    if main is None: # caso não tenha main
        diagnostics.append(SemanticDiagnostic(
            kind=SemanticErrorKind.INVALID_MAIN,
            message="A função 'main' não foi encontrada",
            span=program.span,
        ))
    # se o tipo de retorno não for int ou tem parametros
    elif main.type is not TypeName.INT or main.parameter_types:
        reasons = []
        if main.type is not TypeName.INT:
            reasons.append("o retorno deve ser 'int'")
        if main.parameter_types:
            reasons.append("não deve haver parâmetros")
        diagnostics.append(SemanticDiagnostic(
            kind=SemanticErrorKind.INVALID_MAIN,
            message="Em 'main', " + " e ".join(reasons),
            span=main.declaration.span,
        ))
    # 3. Percorra os corpos em ordem, criando um escopo para cada bloco.
    for function in program.functions:
        scope = Scope(parent=None)                 
        function.body.metadata["scope"] = scope    

        for parameter in function.parameters:
            declare(parameter, SymbolKind.PARAMETER, scope)

        # 4. Anote declarações, usos e blocos na AST.
        for statement in function.body.statements:
            visit_stmt(statement, scope)

    # 5. Acumule os diagnósticos desta passagem antes de lançar SemanticError.
    if diagnostics:
        raise SemanticError(diagnostics)
