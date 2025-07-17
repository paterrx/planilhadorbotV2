# Arquivo: app/services/db_service.py
# Descrição: Gerencia a conexão e as operações com o banco de dados SQLite.

import sqlite3
import os
from app.config import Config

class DbService:
    def __init__(self, cfg: Config):
        self.db_path = cfg.DB_PATH

    def _get_connection(self):
        """Cria e retorna uma conexão com o banco de dados."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        return conn

    def setup_database(self):
        """Cria a tabela de mensagens processadas se ela não existir."""
        conn = self._get_connection()
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (channel_id, message_id)
                )
            ''')
        print("Banco de dados configurado com sucesso.")

    def add_processed_message(self, channel_id, message_id):
        """Adiciona o ID de uma mensagem ao banco de dados para marcar como processada."""
        conn = self._get_connection()
        with conn:
            try:
                conn.execute(
                    'INSERT INTO processed_messages (channel_id, message_id) VALUES (?, ?)',
                    (channel_id, message_id)
                )
            except sqlite3.IntegrityError:
                pass # A mensagem já existe, o que é esperado em alguns casos.

    def is_message_processed(self, channel_id, message_id):
        """Verifica no banco de dados se uma mensagem já foi processada."""
        conn = self._get_connection()
        with conn:
            cursor = conn.execute(
                'SELECT 1 FROM processed_messages WHERE channel_id = ? AND message_id = ?',
                (channel_id, message_id)
            )
            return cursor.fetchone() is not None
