# -*- coding: utf-8 -*-
from collections import defaultdict
from decimal import Decimal
import logging
import traceback
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import date, datetime, time, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required
from helpers.bitacora import bitacora_decorator, registrar_bitacora
from werkzeug.security import generate_password_hash, check_password_hash
from .. import admin_bp

@admin_bp.route('/admin/catalog/metodospagos/metodo-pagos', methods=['GET'])
@admin_required
@bitacora_decorator("METODOS-PAGO")
def admin_metodos_pago():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM Metodos_Pago 
                ORDER BY ID_MetodoPago DESC
            """)
            metodos = cursor.fetchall()
            return render_template('admin/catalog/metodospagos/metodo_pagos.html', 
                                 metodos=metodos)
    except Exception as e:
        flash(f"Error al cargar métodos de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/catalog/metodospagos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-CREAR")
def admin_metodos_pago_crear():
    try:
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre del método de pago es requerido", "danger")
            return redirect(url_for('admin.admin_metodos_pago'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Metodos_Pago (Nombre) 
                VALUES (%s)
            """, (nombre,))

        flash("Método de pago creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear método de pago: {str(e)}", "danger")
    return redirect(url_for('admin.admin_metodos_pago'))


@admin_bp.route('/admin/catalog/metodospagos/editar/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-EDITAR")
def admin_metodos_pago_editar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # GET
            if request.method == 'GET':
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM Metodos_Pago
                    WHERE ID_MetodoPago = %s 
                               """,(id,))
                
                metodo = cursor.fetchone()

                if not metodo:
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                return render_template('admin/catalog/metodospagos/editar_metodo_pago.html',
                                       metodo=metodo)
            
            #POST
            elif request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()

                if not nombre:
                    flash("El nombre del método de pago es requerido", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                        SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s   
                        """, (id,))
                
                if not cursor.fetchone():
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin.admin_metodos_pago'))
                
                cursor.execute("""
                    UPDATE Metodos_Pago
                    SET Nombre = %s
                    WHERE ID_MetodoPago = %s
                    """, (nombre, id))
                
                flash("Metodo d epago actualizado exitosamente", "success")
                return redirect(url_for('admin.admin_metodos_pago'))

    except Exception as e:
        flash(f"Error al editar método de pago: {str(e)}", "danger")
        return redirect(url_for('admin.admin_metodos_pago'))


@admin_bp.route('/admin/catalog/metodospagos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-ELIMINAR")
def admin_metodos_pago_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s
            """, (id,))

            if not cursor.fetchone():
                flash("Método de pago no encontrado.", "danger")
                return redirect(url_for('admin.admin_metodos_pago'))
            
            cursor.execute("""
                DELETE FROM Metodos_Pago
                WHERE ID_MetodoPago = %s
            """, (id,))

        flash("Metodos de pago eliminado exitosamente", "success")
            
    except Exception as e:
        #Manejar error de integridad referencial
        if "foreing key constraint" in str(e).lower():
            flash("No se puede eliminar el método de pago porque está asociado a otros registros.", "danger")
        else:
            flash(f"Error al eliminar método de pago: {str(e)}", "danger")
    
    return redirect(url_for('admin.admin_metodos_pago'))


