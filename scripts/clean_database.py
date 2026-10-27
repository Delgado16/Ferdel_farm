"""
Script para inicializar y limpiar la base de datos db_ferdel.
Limpia todas las transacciones de prueba (ventas, compras, movimientos, inventario, gastos, caja, etc.)
y deja la estructura limpia con los catálogos maestros y los usuarios iniciales:
- Administrador: Admin / admin123
- Vendedor: Vendedor / vendedor123
"""
import os
import sys

# Agregar la raíz del proyecto al sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from werkzeug.security import generate_password_hash
from app import create_app
from config.database import get_db_cursor

def clean_database():
    app = create_app()
    with app.app_context():
        with get_db_cursor(True) as cursor:
            print("🚀 Iniciando limpieza de base de datos db_ferdel...")
            
            # Desactivar verificación de llaves foráneas para truncar tablas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # Lista de tablas transaccionales a vaciar completamente
            tablas_transaccionales = [
                'abonos_detalle',
                'abonos_general',
                'abonos_proveedores_detalle',
                'anticipos_clientes',
                'caja_movimientos',
                'cargas_pendientes_detalle',
                'cargas_pendientes_recepcion',
                'cuentas_por_cobrar',
                'cuentas_por_pagar',
                'detalle_entregas',
                'detalle_facturacion',
                'detalle_facturacion_ruta',
                'detalle_movimientos_inventario',
                'detalle_pedidos',
                'entregas',
                'facturacion',
                'facturacion_ruta',
                'gastos_generales',
                'gastos_vehiculo_detalle',
                'inventario_bodega',
                'inventario_ruta',
                'log_anulaciones',
                'log_cambios_visibilidad',
                'movimientos_caja_ruta',
                'movimientos_inventario',
                'movimientos_ruta_cabecera',
                'movimientos_ruta_detalle',
                'pagos_cuentascobrar',
                'pagos_cuentaspagar',
                'pedidos',
                'pedidos_consolidados_productos',
                'asignacion_vendedores',
                'bitacora',
                'sucursales',
                'clientes',
                'proveedores',
                'productos',
                'usuarios'
            ]
            
            for tabla in tablas_transaccionales:
                try:
                    cursor.execute(f"TRUNCATE TABLE `{tabla}`;")
                    print(f"  ✓ Tabla `{tabla}` vaciada y reiniciada.")
                except Exception as e:
                    print(f"  ⚠️ Error al truncar `{tabla}`: {e}")
            
            # 1. Asegurar Roles
            cursor.execute("TRUNCATE TABLE `roles`;")
            cursor.execute("""
                INSERT INTO `roles` (`ID_Rol`, `Nombre_Rol`, `Estado`) VALUES
                (1, 'Administrador', 'Activo'),
                (2, 'Jefe Galera', 'Inactivo'),
                (3, 'Bodega', 'Activo'),
                (4, 'Vendedor', 'Activo'),
                (5, 'Conductor', 'Activo');
            """)
            print("  ✓ Roles maestros inicializados.")
            
            # 2. Asegurar Empresa
            cursor.execute("TRUNCATE TABLE `empresa`;")
            cursor.execute("""
                INSERT INTO `empresa` (`ID_Empresa`, `Nombre_Empresa`, `Direccion`, `Telefono`, `Estado`, `RUC`) VALUES
                (1, 'GRANJA AVICOLA FERDEL', 'Rastro Municipal 150 mts. Norte, Diriomo', '81006837', 'Activo', '2031407850000U');
            """)
            print("  ✓ Empresa principal configurada.")
            
            # 3. Asegurar Configuración del Sistema
            cursor.execute("TRUNCATE TABLE `config_sistema`;")
            cursor.execute("""
                INSERT INTO `config_sistema` (`llave`, `valor`, `descripcion`) VALUES
                ('empresa_nombre', 'GRANJA AVICOLA FERDEL', 'Nombre de la empresa para reportes y comprobantes'),
                ('empresa_direccion', 'Rastro Municipal 150 mts. Norte, Diriomo', 'Dirección física de la empresa'),
                ('empresa_telefono', '81006837', 'Teléfono de contacto general'),
                ('empresa_ruc', '2031407850000U', 'RUC/Identificación fiscal de la empresa'),
                ('iva_porcentaje', '0.0', 'Porcentaje de impuesto al valor agregado (IVA)'),
                ('smtp_host', 'smtp.gmail.com', 'Servidor de correo SMTP'),
                ('smtp_port', '587', 'Puerto del servidor SMTP'),
                ('smtp_user', '', 'Usuario/Correo del servidor SMTP'),
                ('smtp_password', '', 'Contraseña de aplicación SMTP');
            """)
            print("  ✓ Configuración del sistema inicializada.")
            
            # 4. Asegurar Unidades de Medida
            cursor.execute("TRUNCATE TABLE `unidades_medida`;")
            cursor.execute("""
                INSERT INTO `unidades_medida` (`ID_Unidad`, `Descripcion`, `Abreviatura`) VALUES
                (1, 'Caja', 'CJA'),
                (2, 'Docena', 'DOC'),
                (3, 'Unidad', 'UND'),
                (4, 'Libra', 'LB'),
                (5, 'Quintal', 'QQ');
            """)
            print("  ✓ Unidades de medida inicializadas.")
            
            # 5. Asegurar Categorías de Producto
            cursor.execute("TRUNCATE TABLE `categorias_producto`;")
            cursor.execute("""
                INSERT INTO `categorias_producto` (`ID_Categoria`, `Descripcion`, `Estado`) VALUES
                (1, 'Huevos', 'Activo'),
                (2, 'Aves de Corral', 'Activo'),
                (3, 'Alimento Balanceado', 'Activo'),
                (4, 'Insumos y Materiales', 'Activo');
            """)
            print("  ✓ Categorías de producto inicializadas.")
            
            # 6. Asegurar Métodos de Pago
            cursor.execute("TRUNCATE TABLE `metodos_pago`;")
            cursor.execute("""
                INSERT INTO `metodos_pago` (`ID_MetodoPago`, `Nombre`) VALUES
                (1, 'Efectivo'),
                (2, 'Transferencia'),
                (3, 'Tarjeta'),
                (4, 'Cheque');
            """)
            print("  ✓ Métodos de pago inicializados.")
            
            # 7. Asegurar Catálogo de Movimientos
            cursor.execute("TRUNCATE TABLE `catalogo_movimientos`;")
            cursor.execute("""
                INSERT INTO `catalogo_movimientos` (`ID_TipoMovimiento`, `Descripcion`, `Adicion`, `Letra`) VALUES
                (1, 'Entrada por Compra', 'SI', 'C'),
                (2, 'Salida por Venta', 'NO', 'V'),
                (3, 'Carga a Ruta', 'NO', 'CR'),
                (4, 'Devolución de Ruta', 'SI', 'DR'),
                (5, 'Ajuste Positivo', 'SI', 'AP'),
                (6, 'Ajuste Negativo', 'NO', 'AN'),
                (7, 'Transferencia entre Bodegas', 'NO', 'TB');
            """)
            print("  ✓ Catálogo de movimientos de inventario inicializado.")
            
            # 8. Asegurar Tipos de Gasto y Subcategorías
            cursor.execute("TRUNCATE TABLE `subcategorias_gasto`;")
            cursor.execute("TRUNCATE TABLE `tipos_gasto`;")
            cursor.execute("""
                INSERT INTO `tipos_gasto` (`ID_Tipo_Gasto`, `Nombre`, `Descripcion`, `Origen`, `ID_Empresa`, `Estado`) VALUES
                (1, 'Servicios Públicos', 'Agua, Luz, Internet, Telefonía', 'GASTO_DIRECTO', 1, 'Activo'),
                (2, 'Vehículos y Transporte', 'Combustible, Mantenimiento y Talleres de Flota', 'GASTO_DIRECTO', 1, 'Activo'),
                (3, 'Gastos Operativos', 'Viáticos, Papelería, Aseo y Limpieza', 'GASTO_DIRECTO', 1, 'Activo'),
                (4, 'Mantenimiento General', 'Reparaciones locativas e infraestructura', 'GASTO_DIRECTO', 1, 'Activo');
            """)
            cursor.execute("""
                INSERT INTO `subcategorias_gasto` (`ID_Subcategoria`, `ID_Tipo_Gasto`, `Nombre`, `Descripcion`, `Estado`) VALUES
                (1, 1, 'Energía Eléctrica', 'Pago mensual de servicio de luz', 'Activo'),
                (2, 1, 'Agua Potable', 'Pago mensual de servicio de agua', 'Activo'),
                (3, 1, 'Internet y Conectividad', 'Servicio de internet y enlaces', 'Activo'),
                (4, 1, 'Telefonía Móvil', 'Planes de llamadas corporativas', 'Activo'),
                (5, 2, 'Combustible', 'Gasolina o Diesel para vehículos de ruta y entrega', 'Activo'),
                (6, 2, 'Mantenimiento Preventivo', 'Cambio de aceite, filtros y chequeos', 'Activo'),
                (7, 2, 'Llantas y Neumáticos', 'Reemplazo o parchado de llantas', 'Activo'),
                (8, 2, 'Reparación Mecánica', 'Reparaciones en taller por avería', 'Activo'),
                (9, 3, 'Alimentación / Viáticos', 'Viáticos de personal en ruta', 'Activo'),
                (10, 3, 'Papelería y Útiles', 'Hojas, facturas, tinta y suministros', 'Activo'),
                (11, 4, 'Mantenimiento de Galeras', 'Reparaciones en infraestructura de producción', 'Activo');
            """)
            print("  ✓ Tipos y subcategorías de gasto inicializados.")
            
            # 9. Asegurar Bodega Principal
            cursor.execute("TRUNCATE TABLE `bodegas`;")
            cursor.execute("""
                INSERT INTO `bodegas` (`ID_Bodega`, `Nombre`, `Ubicacion`, `Estado`, `ID_Empresa`) VALUES
                (1, 'Bodega Central', 'Diriomo, Granada', 'activa', 1);
            """)
            print("  ✓ Bodega central inicializada.")
            
            # 10. Asegurar Rutas
            cursor.execute("TRUNCATE TABLE `rutas`;")
            cursor.execute("""
                INSERT INTO `rutas` (`ID_Ruta`, `Nombre_Ruta`, `Descripcion`, `ID_Empresa`, `Estado`) VALUES
                (1, 'Ruta Central', 'Diriomo, Diriá, Guanacaste y Granada', 1, 'Activa'),
                (2, 'Ruta Managua', 'Distribución Managua y alrededores', 1, 'Activa'),
                (3, 'Ruta Masaya', 'Distribución Masaya y pueblos blancos', 1, 'Activa');
            """)
            print("  ✓ Rutas de venta inicializadas.")
            
            # 11. Asegurar Vehículos
            cursor.execute("TRUNCATE TABLE `vehiculos`;")
            cursor.execute("""
                INSERT INTO `vehiculos` (`ID_Vehiculo`, `Placa`, `Marca`, `Modelo`, `Anio`, `Estado`, `ID_Empresa`, `Tipo_Combustible`) VALUES
                (1, 'GR-10293', 'Toyota', 'Hilux 4x4', 2024, 'Disponible', 1, 'Diesel'),
                (2, 'M-293841', 'Hyundai', 'H100', 2023, 'Disponible', 1, 'Diesel');
            """)
            print("  ✓ Vehículos de flota inicializados.")
            
            # 12. Crear Usuarios (Administrador y Vendedor)
            pass_admin = generate_password_hash("admin123")
            pass_vendedor = generate_password_hash("vendedor123")
            
            cursor.execute("""
                INSERT INTO `usuarios` (`ID_Usuario`, `NombreUsuario`, `Contraseña`, `ID_Rol`, `Estado`, `Fecha_Creacion`, `ID_Empresa`) VALUES
                (1, 'Admin', %s, 1, 'ACTIVO', CURDATE(), 1),
                (2, 'Vendedor', %s, 4, 'ACTIVO', CURDATE(), 1);
            """, (pass_admin, pass_vendedor))
            print("  ✓ Usuarios creados:")
            print("     - Administrador: 'Admin' (Contraseña: 'admin123')")
            print("     - Vendedor:      'Vendedor' (Contraseña: 'vendedor123')")
            
            # 13. Asignación inicial de Ruta para el Vendedor
            cursor.execute("""
                INSERT INTO `asignacion_vendedores` (
                    `ID_Asignacion`, `ID_Usuario`, `ID_Ruta`, `ID_Vehiculo`,
                    `Fecha_Asignacion`, `Estado`, `ID_Empresa`, `ID_Usuario_Asigna`
                ) VALUES (
                    1, 2, 1, 1, CURDATE(), 'Activa', 1, 1
                );
            """)
            print("  ✓ Asignación de ruta activa configurada para el Vendedor (Ruta Central / Vehículo GR-10293).")
            
            # 14. Productos iniciales limpios (con stock 0)
            cursor.execute("""
                INSERT INTO `productos` (
                    `ID_Producto`, `COD_Producto`, `Descripcion`, `Unidad_Medida`,
                    `Estado`, `ID_Categoria`, `Precio_Mercado`, `Precio_Mayorista`, `Precio_Ruta`,
                    `ID_Empresa`, `Usuario_Creador`, `Stock_Minimo`
                ) VALUES
                (1, 'HUE-GDE-01', 'Huevo Blanco Grande', 1, 'activo', 1, 140.00, 130.00, 135.00, 1, 1, 10.00),
                (2, 'HUE-MED-02', 'Huevo Blanco Mediano', 1, 'activo', 1, 125.00, 115.00, 120.00, 1, 1, 10.00),
                (3, 'HUE-EXT-03', 'Huevo Jumbo Especial', 1, 'activo', 1, 155.00, 145.00, 150.00, 1, 1, 5.00);
            """)
            print("  ✓ Productos base inicializados (stock en 0).")
            
            # Reactivar llaves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
            print("\n🎉 BASE DE DATOS LIMPIA Y PREPARADA CON ÉXITO!")

if __name__ == '__main__':
    clean_database()
