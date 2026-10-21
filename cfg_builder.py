"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import (
    Assignment,
    Block,
    BoolLiteral,
    CallStmt,
    FunctionDecl,
    IfStmt,
    PrintStmt,
    ReturnStmt,
    Stmt,
    VarDecl,
    WhileStmt,
)
from cfg import BlockId, CFG, Branch, Jump, Return, ScopeExit


class CFGBuilder:
    def build(self, function: FunctionDecl) -> CFG:
        self.cfg = CFG(function)
        body_entry = self.cfg.new_block()
        self.cfg.terminate(self.cfg.entry, Jump(body_entry.id))
        continuation = self._build_block(function.body, body_entry.id)
        if continuation is not None:
            self.cfg.terminate(continuation, Jump(self.cfg.fallthrough_exit))
        return self.cfg

    def _build_block(self, block: Block, current: BlockId) -> BlockId | None:
        """Percorra um bloco da AST e devolva sua continuação normal.

        `current` identifica um bloco básico aberto. Comandos sequenciais
        permanecem nele. Comandos de controle podem mudar a continuação.
        None indica que os caminhos deste bloco não alcançam o próximo comando.
        """
        for statement in block.statements:
            current = self._build_statement(statement, current)
            if current is None:
                return None
        
        self.cfg.blocks[current].operations.append(ScopeExit(block.metadata["scope"]))
        return current

    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """TODO: incorpore um comando ao CFG e devolva sua continuação normal."""

        if isinstance(statement, (VarDecl, Assignment, PrintStmt, CallStmt)):
            self.cfg.blocks[current].operations.append(statement)
            return current
        
        if isinstance(statement, Block):
            return self._build_block(statement,current)
        
        if isinstance(statement,ReturnStmt):
            self.cfg.terminate(current,Return(statement))
            return None
        
        if isinstance(statement,IfStmt):
            return self._build_if(statement,current)
        
        if isinstance(statement, WhileStmt):
            return self._build_while(statement,current)
        
        raise TypeError(f"o que eh isso: {type(statement).__name__}")

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        then_entry = self.cfg.new_block()

        if statement.else_block is not None:
            else_entry = self.cfg.new_block()
            self.cfg.terminate(current, Branch(statement.condition, then_entry.id, else_entry.id))

            then_exit = self._build_block(statement.then_block, then_entry.id)
            else_exit = self._build_block(statement.else_block, else_entry.id)

            if then_exit is None and else_exit is None:
                return None

            join_block = self.cfg.new_block()
            if then_exit is not None:
                self.cfg.terminate(then_exit, Jump(join_block.id))
            if else_exit is not None:
                self.cfg.terminate(else_exit, Jump(join_block.id))
            return join_block.id

        # Sem else: o caminho falso vai direto para a junção
        join_block = self.cfg.new_block()
        self.cfg.terminate(current, Branch(statement.condition, then_entry.id, join_block.id))

        then_exit = self._build_block(statement.then_block, then_entry.id)
        if then_exit is not None:
            self.cfg.terminate(then_exit, Jump(join_block.id))
        return join_block.id

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        header = self.cfg.new_block()
        self.cfg.terminate(current, Jump(header.id))

        body_entry = self.cfg.new_block()

        is_infinite = (
            isinstance(statement.condition, BoolLiteral)
            and statement.condition.value is True
        )

        if is_infinite:
            self.cfg.terminate(header.id, Jump(body_entry.id))
            body_exit = self._build_block(statement.body, body_entry.id)
            if body_exit is not None:
                self.cfg.terminate(body_exit, Jump(header.id))
            return None

        exit_block = self.cfg.new_block()
        self.cfg.terminate(
            header.id,
            Branch(statement.condition, body_entry.id, exit_block.id),
        )
        body_exit = self._build_block(statement.body, body_entry.id)
        if body_exit is not None:
            self.cfg.terminate(body_exit, Jump(header.id))
        return exit_block.id
