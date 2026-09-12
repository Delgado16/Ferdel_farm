-- ========================================================
-- BASE DE DATOS LIMPIA: db_ferdel
-- Sistema de Gestión Granja Avícola FerDel
-- Contiene DDL completo, vistas, relaciones y datos maestros limpios
-- Usuarios incluidos:
--   1) Administrador: Admin (admin123)
--   2) Vendedor:      Vendedor (vendedor123)
-- ========================================================

CREATE DATABASE IF NOT EXISTS `db_ferdel` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE `db_ferdel`;

SET FOREIGN_KEY_CHECKS = 0;

-- --------------------------------------------------------
-- 1. TABLAS MAESTRAS Y DE CONFIGURACIÓN
-- --------------------------------------------------------

DROP TABLE IF EXISTS `empresa`;
CREATE TABLE `empresa` (
  `ID_Empresa` int NOT NULL AUTO_INCREMENT,
  `Nombre_Empresa` varchar(255) NOT NULL,
  `Direccion` varchar(240) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `RUC` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`ID_Empresa`),
  KEY `idx_empresa_estado` (`Estado`),
  KEY `idx_empresa_nombre` (`Nombre_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `empresa` (`ID_Empresa`, `Nombre_Empresa`, `Direccion`, `Telefono`, `Estado`, `RUC`) VALUES
(1, 'GRANJA AVICOLA FERDEL', 'Rastro Municipal 150 mts. Norte, Diriomo', '81006837', 'Activo', '2031407850000U');

DROP TABLE IF EXISTS `config_sistema`;
CREATE TABLE `config_sistema` (
  `llave` varchar(100) NOT NULL,
  `valor` text,
  `descripcion` varchar(255) DEFAULT NULL,
  `fecha_actualizacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`llave`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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

DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  `Estado` enum('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `roles` (`ID_Rol`, `Nombre_Rol`, `Estado`) VALUES
(1, 'Administrador', 'Activo'),
(2, 'Jefe Galera', 'Inactivo'),
(3, 'Bodega', 'Activo'),
(4, 'Vendedor', 'Activo'),
(5, 'Conductor', 'Activo');

DROP TABLE IF EXISTS `usuarios`;
CREATE TABLE `usuarios` (
  `ID_Usuario` int NOT NULL AUTO_INCREMENT,
  `NombreUsuario` varchar(255) NOT NULL,
  `Contraseña` varchar(255) NOT NULL,
  `ID_Rol` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO','BLOQUEADO','PENDIENTE') DEFAULT 'ACTIVO',
  `Fecha_Creacion` date DEFAULT (curdate()),
  `ID_Empresa` int NOT NULL,
  PRIMARY KEY (`ID_Usuario`),
  UNIQUE KEY `NombreUsuario` (`NombreUsuario`),
  KEY `ID_Rol` (`ID_Rol`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `usuarios_ibfk_1` FOREIGN KEY (`ID_Rol`) REFERENCES `roles` (`ID_Rol`),
  CONSTRAINT `usuarios_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Contraseña para Admin: admin123 | Contraseña para Vendedor: vendedor123
INSERT INTO `usuarios` (`ID_Usuario`, `NombreUsuario`, `Contraseña`, `ID_Rol`, `Estado`, `Fecha_Creacion`, `ID_Empresa`) VALUES
(1, 'Admin', 'scrypt:32768:8:1$99EXvvfxRrQwInGY$324d6ce1a9c171398137d6c042f24fadc2f8d3a40ecb758758010419e42b507a3423e4c06c56fc18cb47e99ffeb75d2cf3253c3b34efdabcc31059c23819fe8f', 1, 'ACTIVO', CURDATE(), 1),
(2, 'Vendedor', 'scrypt:32768:8:1$WdLWkdlDTN67K1bs$a4132767197dd56be6b721eb20e91fdf8b13400d238dcb9fc5b06fdbc3701166aeca488f83743ea4ba0157f626156a045cc1491b99c90b7d23d45bfc0acbd333', 4, 'ACTIVO', CURDATE(), 1);

DROP TABLE IF EXISTS `unidades_medida`;
CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`),
  UNIQUE KEY `uc_descripcion` (`Descripcion`),
  UNIQUE KEY `uc_abreviatura` (`Abreviatura`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `unidades_medida` (`ID_Unidad`, `Descripcion`, `Abreviatura`) VALUES
(1, 'Caja', 'CJA'),
(2, 'Docena', 'DOC'),
(3, 'Unidad', 'UND'),
(4, 'Libra', 'LB'),
(5, 'Quintal', 'QQ');

DROP TABLE IF EXISTS `categorias_producto`;
CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Estado` enum('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `categorias_producto` (`ID_Categoria`, `Descripcion`, `Estado`) VALUES
(1, 'Huevos', 'Activo'),
(2, 'Aves de Corral', 'Activo'),
(3, 'Alimento Balanceado', 'Activo'),
(4, 'Insumos y Materiales', 'Activo');

DROP TABLE IF EXISTS `metodos_pago`;
CREATE TABLE `metodos_pago` (
  `ID_MetodoPago` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_MetodoPago`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `metodos_pago` (`ID_MetodoPago`, `Nombre`) VALUES
(1, 'Efectivo'),
(2, 'Transferencia'),
(3, 'Tarjeta'),
(4, 'Cheque');

DROP TABLE IF EXISTS `catalogo_movimientos`;
CREATE TABLE `catalogo_movimientos` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `catalogo_movimientos` (`ID_TipoMovimiento`, `Descripcion`, `Adicion`, `Letra`) VALUES
(1, 'Entrada por Compra', 'SI', 'C'),
(2, 'Salida por Venta', 'NO', 'V'),
(3, 'Carga a Ruta', 'NO', 'CR'),
(4, 'Devolución de Ruta', 'SI', 'DR'),
(5, 'Ajuste Positivo', 'SI', 'AP'),
(6, 'Ajuste Negativo', 'NO', 'AN'),
(7, 'Transferencia entre Bodegas', 'NO', 'TB');

DROP TABLE IF EXISTS `bodegas`;
CREATE TABLE `bodegas` (
  `ID_Bodega` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Ubicacion` varchar(255) DEFAULT NULL,
  `Estado` enum('activa','inactiva') DEFAULT 'activa',
  `ID_Empresa` int NOT NULL,
  `Fecha_Creacion` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Bodega`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `bodegas_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `bodegas` (`ID_Bodega`, `Nombre`, `Ubicacion`, `Estado`, `ID_Empresa`) VALUES
(1, 'Bodega Central', 'Diriomo, Granada', 'activa', 1);

DROP TABLE IF EXISTS `rutas`;
CREATE TABLE `rutas` (
  `ID_Ruta` int NOT NULL AUTO_INCREMENT,
  `Nombre_Ruta` varchar(255) NOT NULL,
  `Descripcion` text,
  `ID_Empresa` int NOT NULL,
  `Estado` enum('Activa','Inactiva') DEFAULT 'Activa',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Ruta`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `rutas_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `rutas` (`ID_Ruta`, `Nombre_Ruta`, `Descripcion`, `ID_Empresa`, `Estado`) VALUES
(1, 'Ruta Central', 'Diriomo, Diriá, Guanacaste y Granada', 1, 'Activa'),
(2, 'Ruta Managua', 'Distribución Managua y alrededores', 1, 'Activa'),
(3, 'Ruta Masaya', 'Distribución Masaya y pueblos blancos', 1, 'Activa');

DROP TABLE IF EXISTS `vehiculos`;
CREATE TABLE `vehiculos` (
  `ID_Vehiculo` int NOT NULL AUTO_INCREMENT,
  `Placa` varchar(20) NOT NULL,
  `Marca` varchar(100) DEFAULT NULL,
  `Modelo` varchar(100) DEFAULT NULL,
  `Anio` year DEFAULT NULL,
  `Estado` enum('Disponible','En Ruta','Mantenimiento','Inactivo') DEFAULT 'Disponible',
  `ID_Empresa` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Vencimiento_Seguro` date DEFAULT NULL,
  `Tipo_Combustible` enum('Gasolina','Diesel') NOT NULL DEFAULT 'Gasolina',
  PRIMARY KEY (`ID_Vehiculo`),
  UNIQUE KEY `uc_placa_empresa` (`Placa`,`ID_Empresa`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `vehiculos_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `vehiculos` (`ID_Vehiculo`, `Placa`, `Marca`, `Modelo`, `Anio`, `Estado`, `ID_Empresa`, `Tipo_Combustible`) VALUES
(1, 'GR-10293', 'Toyota', 'Hilux 4x4', 2024, 'Disponible', 1, 'Diesel'),
(2, 'M-293841', 'Hyundai', 'H100', 2023, 'Disponible', 1, 'Diesel');

DROP TABLE IF EXISTS `asignacion_vendedores`;
CREATE TABLE `asignacion_vendedores` (
  `ID_Asignacion` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int NOT NULL COMMENT 'Vendedor',
  `ID_Ruta` int NOT NULL,
  `ID_Vehiculo` int DEFAULT NULL,
  `Fecha_Asignacion` date NOT NULL,
  `Fecha_Finalizacion` date DEFAULT NULL,
  `Estado` enum('Activa','Finalizada','Suspendida') DEFAULT 'Activa',
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Asigna` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Hora_Inicio` time DEFAULT NULL,
  `Hora_Fin` time DEFAULT NULL,
  PRIMARY KEY (`ID_Asignacion`),
  KEY `ID_Ruta` (`ID_Ruta`),
  KEY `ID_Vehiculo` (`ID_Vehiculo`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Asigna` (`ID_Usuario_Asigna`),
  KEY `idx_vendedor` (`ID_Usuario`),
  CONSTRAINT `asignacion_vendedores_ibfk_1` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `asignacion_vendedores_ibfk_2` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`),
  CONSTRAINT `asignacion_vendedores_ibfk_3` FOREIGN KEY (`ID_Vehiculo`) REFERENCES `vehiculos` (`ID_Vehiculo`),
  CONSTRAINT `asignacion_vendedores_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `asignacion_vendedores_ibfk_5` FOREIGN KEY (`ID_Usuario_Asigna`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `asignacion_vendedores` (`ID_Asignacion`, `ID_Usuario`, `ID_Ruta`, `ID_Vehiculo`, `Fecha_Asignacion`, `Estado`, `ID_Empresa`, `ID_Usuario_Asigna`) VALUES
(1, 2, 1, 1, CURDATE(), 'Activa', 1, 1);

DROP TABLE IF EXISTS `tipos_gasto`;
CREATE TABLE `tipos_gasto` (
  `ID_Tipo_Gasto` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(50) NOT NULL,
  `Descripcion` text,
  `Origen` enum('INVENTARIO','GASTO_DIRECTO') DEFAULT 'GASTO_DIRECTO',
  `ID_Categoria_Inventario` int DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `ID_Empresa` int DEFAULT NULL,
  PRIMARY KEY (`ID_Tipo_Gasto`),
  KEY `ID_Categoria_Inventario` (`ID_Categoria_Inventario`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `fk_tipos_gasto_categoria_inv` FOREIGN KEY (`ID_Categoria_Inventario`) REFERENCES `categorias_producto` (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `tipos_gasto` (`ID_Tipo_Gasto`, `Nombre`, `Descripcion`, `Origen`, `ID_Empresa`, `Estado`) VALUES
(1, 'Servicios Públicos', 'Agua, Luz, Internet, Telefonía', 'GASTO_DIRECTO', 1, 'Activo'),
(2, 'Vehículos y Transporte', 'Combustible, Mantenimiento y Talleres de Flota', 'GASTO_DIRECTO', 1, 'Activo'),
(3, 'Gastos Operativos', 'Viáticos, Papelería, Aseo y Limpieza', 'GASTO_DIRECTO', 1, 'Activo'),
(4, 'Mantenimiento General', 'Reparaciones locativas e infraestructura', 'GASTO_DIRECTO', 1, 'Activo');

DROP TABLE IF EXISTS `subcategorias_gasto`;
CREATE TABLE `subcategorias_gasto` (
  `ID_Subcategoria` int NOT NULL AUTO_INCREMENT,
  `ID_Tipo_Gasto` int NOT NULL,
  `Nombre` varchar(50) NOT NULL,
  `Descripcion` text,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  PRIMARY KEY (`ID_Subcategoria`),
  KEY `ID_Tipo_Gasto` (`ID_Tipo_Gasto`),
  CONSTRAINT `fk_subcategoria_tipo_gasto` FOREIGN KEY (`ID_Tipo_Gasto`) REFERENCES `tipos_gasto` (`ID_Tipo_Gasto`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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

DROP TABLE IF EXISTS `productos`;
CREATE TABLE `productos` (
  `ID_Producto` int NOT NULL AUTO_INCREMENT,
  `COD_Producto` varchar(100) DEFAULT NULL,
  `Descripcion` varchar(255) NOT NULL,
  `Unidad_Medida` int DEFAULT NULL,
  `Estado` enum('activo','inactivo') DEFAULT 'activo',
  `ID_Categoria` int DEFAULT NULL,
  `Precio_Mercado` decimal(12,2) DEFAULT NULL,
  `Precio_Mayorista` decimal(12,2) DEFAULT NULL,
  `Precio_Ruta` decimal(12,2) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Usuario_Creador` int DEFAULT NULL,
  `Stock_Minimo` decimal(12,2) DEFAULT '5.00',
  PRIMARY KEY (`ID_Producto`),
  KEY `Unidad_Medida` (`Unidad_Medida`),
  KEY `ID_Categoria` (`ID_Categoria`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `Usuario_Creador` (`Usuario_Creador`),
  CONSTRAINT `productos_ibfk_1` FOREIGN KEY (`Unidad_Medida`) REFERENCES `unidades_medida` (`ID_Unidad`),
  CONSTRAINT `productos_ibfk_2` FOREIGN KEY (`ID_Categoria`) REFERENCES `categorias_producto` (`ID_Categoria`),
  CONSTRAINT `productos_ibfk_3` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `productos_ibfk_4` FOREIGN KEY (`Usuario_Creador`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `productos` (`ID_Producto`, `COD_Producto`, `Descripcion`, `Unidad_Medida`, `Estado`, `ID_Categoria`, `Precio_Mercado`, `Precio_Mayorista`, `Precio_Ruta`, `ID_Empresa`, `Usuario_Creador`, `Stock_Minimo`) VALUES
(1, 'HUE-GDE-01', 'Huevo Blanco Grande', 1, 'activo', 1, 140.00, 130.00, 135.00, 1, 1, 10.00),
(2, 'HUE-MED-02', 'Huevo Blanco Mediano', 1, 'activo', 1, 125.00, 115.00, 120.00, 1, 1, 10.00),
(3, 'HUE-EXT-03', 'Huevo Jumbo Especial', 1, 'activo', 1, 155.00, 145.00, 150.00, 1, 1, 5.00);

DROP TABLE IF EXISTS `config_visibilidad_categorias`;
CREATE TABLE `config_visibilidad_categorias` (
  `ID_Config` int NOT NULL AUTO_INCREMENT,
  `tipo_cliente` enum('Comun','Especial') NOT NULL,
  `ID_Categoria` int NOT NULL,
  `visible` tinyint(1) DEFAULT '0',
  `fecha_creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Config`),
  UNIQUE KEY `unico_tipo_categoria` (`tipo_cliente`,`ID_Categoria`),
  KEY `ID_Categoria` (`ID_Categoria`),
  CONSTRAINT `fk_config_categoria` FOREIGN KEY (`ID_Categoria`) REFERENCES `categorias_producto` (`ID_Categoria`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `clientes`;
CREATE TABLE `clientes` (
  `ID_Cliente` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `ID_Ruta` int DEFAULT NULL,
  `Saldo_Pendiente_Total` decimal(12,2) DEFAULT '0.00',
  `Fecha_Ultimo_Movimiento` datetime DEFAULT NULL,
  `ID_Ultima_Factura` int DEFAULT NULL,
  `Fecha_Ultimo_Pago` datetime DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `tipo_cliente` enum('Comun','Especial') NOT NULL DEFAULT 'Comun',
  `perfil_cliente` enum('Ruta','Mayorista','Mercado','Especial') NOT NULL DEFAULT 'Mercado',
  `Anticipo_Activo` tinyint(1) DEFAULT '0',
  `Limite_Anticipo_Cajas` int DEFAULT '0',
  `Cajas_Consumidas_Anticipo` int DEFAULT '0',
  `Saldo_Anticipos` decimal(12,2) DEFAULT '0.00',
  `Producto_Anticipado` int DEFAULT NULL,
  PRIMARY KEY (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_clientes_busqueda` (`ID_Empresa`,`Estado`,`Nombre`),
  KEY `idx_clientes_ruta` (`ID_Ruta`),
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `clientes_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `clientes_ibfk_ruta` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `sucursales`;
CREATE TABLE `sucursales` (
  `ID_Sucursal` int NOT NULL AUTO_INCREMENT,
  `ID_Cliente` int NOT NULL,
  `Nombre_Sucursal` varchar(255) NOT NULL,
  `Direccion` text,
  `Telefono` varchar(50) DEFAULT NULL,
  `Encargado` varchar(255) DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Sucursal`),
  KEY `ID_Cliente` (`ID_Cliente`),
  CONSTRAINT `sucursales_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `proveedores`;
CREATE TABLE `proveedores` (
  `ID_Proveedor` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Saldo_Pendiente` decimal(12,2) DEFAULT '0.00',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Proveedor`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `proveedores_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `proveedores_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- 2. TABLAS TRANSACCIONALES (LIMPIAS)
-- --------------------------------------------------------

DROP TABLE IF EXISTS `pedidos`;
CREATE TABLE `pedidos` (
  `ID_Pedido` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `ID_Cliente` int DEFAULT NULL,
  `ID_Empresa` int NOT NULL,
  `ID_Ruta` int DEFAULT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Aprobado','Entregado','Cancelado') DEFAULT 'Pendiente',
  `Observacion` text,
  `Tipo_Entrega` enum('Retiro en local','Entrega a domicilio') DEFAULT 'Retiro en local',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Prioridad` enum('Urgente','Normal','Bajo') NOT NULL DEFAULT 'Normal',
  `Tipo_Pedido` enum('Individual','Consolidado') NOT NULL DEFAULT 'Individual',
  `Es_Pedido_Ruta` enum('SI','NO') NOT NULL DEFAULT 'NO',
  PRIMARY KEY (`ID_Pedido`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `ID_Ruta` (`ID_Ruta`),
  CONSTRAINT `pedidos_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `pedidos_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `pedidos_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `pedidos_ibfk_ruta` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `detalle_pedidos`;
CREATE TABLE `detalle_pedidos` (
  `ID_Detalle_Pedido` int NOT NULL AUTO_INCREMENT,
  `ID_Pedido` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Precio_Unitario` decimal(12,2) NOT NULL,
  `Cantidad` decimal(12,2) NOT NULL,
  `Subtotal` decimal(12,2) NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Detalle_Pedido`),
  KEY `ID_Pedido` (`ID_Pedido`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `detalle_pedidos_ibfk_1` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`) ON DELETE CASCADE,
  CONSTRAINT `detalle_pedidos_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `pedidos_consolidados_productos`;
CREATE TABLE `pedidos_consolidados_productos` (
  `ID_Pedido_Consolidado_Producto` int NOT NULL AUTO_INCREMENT,
  `ID_Pedido` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Total` decimal(12,2) NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Pedido_Consolidado_Producto`),
  UNIQUE KEY `unique_pedido_producto` (`ID_Pedido`,`ID_Producto`),
  KEY `ID_Pedido` (`ID_Pedido`),
  KEY `ID_Producto` (`ID_Producto`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `pedidos_consolidados_productos_ibfk_1` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`) ON DELETE CASCADE,
  CONSTRAINT `pedidos_consolidados_productos_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`),
  CONSTRAINT `pedidos_consolidados_productos_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `facturacion`;
CREATE TABLE `facturacion` (
  `ID_Factura` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `IDCliente` int NOT NULL,
  `Credito_Contado` int DEFAULT NULL,
  `Observacion` text,
  `metodos_pago` json DEFAULT NULL,
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Estado` enum('Activa','Anulada') NOT NULL DEFAULT 'Activa',
  `ID_Pedido` int DEFAULT NULL,
  `Saldo_Anterior_Cliente` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`ID_Factura`),
  KEY `IDCliente` (`IDCliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_facturacion_pedido` (`ID_Pedido`),
  CONSTRAINT `facturacion_ibfk_1` FOREIGN KEY (`IDCliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `facturacion_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `facturacion_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `fk_facturacion_pedido` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `detalle_facturacion`;
CREATE TABLE `detalle_facturacion` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Factura` int DEFAULT NULL,
  `ID_Producto` int DEFAULT NULL,
  `Cantidad` decimal(12,2) DEFAULT NULL,
  `Costo` decimal(12,2) DEFAULT NULL,
  `Total` decimal(12,2) DEFAULT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Factura` (`ID_Factura`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `detalle_facturacion_ibfk_1` FOREIGN KEY (`ID_Factura`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `detalle_facturacion_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `movimientos_ruta_cabecera`;
CREATE TABLE `movimientos_ruta_cabecera` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_Asignacion` int NOT NULL,
  `ID_TipoMovimiento` int NOT NULL,
  `Fecha_Movimiento` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Registra` int NOT NULL,
  `Documento_Numero` varchar(50) DEFAULT NULL,
  `ID_Cliente` int DEFAULT NULL,
  `ID_Pedido` int DEFAULT NULL,
  `Total_Productos` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Total_Items` int NOT NULL DEFAULT '0',
  `Total_Subtotal` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Monto_Efectivo` decimal(12,2) DEFAULT '0.00',
  `ID_Empresa` int NOT NULL,
  `Estado` enum('ACTIVO','ANULADO') DEFAULT 'ACTIVO',
  `Fecha_Anulacion` datetime DEFAULT NULL,
  `ID_Usuario_Anula` int DEFAULT NULL,
  `Motivo_Anulacion` text,
  PRIMARY KEY (`ID_Movimiento`),
  KEY `idx_asignacion` (`ID_Asignacion`),
  KEY `idx_tipo` (`ID_TipoMovimiento`),
  KEY `idx_fecha` (`Fecha_Movimiento`),
  KEY `idx_cliente` (`ID_Cliente`),
  KEY `idx_pedido` (`ID_Pedido`),
  KEY `idx_documento` (`Documento_Numero`),
  KEY `idx_estado` (`Estado`),
  KEY `idx_empresa` (`ID_Empresa`),
  KEY `fk_movcab_usuario_reg` (`ID_Usuario_Registra`),
  KEY `fk_movcab_usuario_anu` (`ID_Usuario_Anula`),
  CONSTRAINT `fk_movcab_asignacion` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `fk_movcab_cliente` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`) ON DELETE SET NULL,
  CONSTRAINT `fk_movcab_empresa` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `fk_movcab_pedido` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`) ON DELETE SET NULL,
  CONSTRAINT `fk_movcab_tipo` FOREIGN KEY (`ID_TipoMovimiento`) REFERENCES `catalogo_movimientos` (`ID_TipoMovimiento`),
  CONSTRAINT `fk_movcab_usuario_anu` FOREIGN KEY (`ID_Usuario_Anula`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `fk_movcab_usuario_reg` FOREIGN KEY (`ID_Usuario_Registra`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `movimientos_ruta_detalle`;
CREATE TABLE `movimientos_ruta_detalle` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad` decimal(12,2) NOT NULL,
  `Precio_Unitario` decimal(12,2) NOT NULL,
  `Subtotal` decimal(12,2) NOT NULL,
  `ID_Detalle_Pedido` int DEFAULT NULL,
  `ID_Movimiento_Origen` int DEFAULT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `idx_movimiento` (`ID_Movimiento`),
  KEY `idx_producto` (`ID_Producto`),
  KEY `idx_detalle_pedido` (`ID_Detalle_Pedido`),
  KEY `idx_movimiento_origen` (`ID_Movimiento_Origen`),
  CONSTRAINT `fk_movdet_detalle_pedido` FOREIGN KEY (`ID_Detalle_Pedido`) REFERENCES `detalle_pedidos` (`ID_Detalle_Pedido`) ON DELETE SET NULL,
  CONSTRAINT `fk_movdet_movimiento` FOREIGN KEY (`ID_Movimiento`) REFERENCES `movimientos_ruta_cabecera` (`ID_Movimiento`) ON DELETE CASCADE,
  CONSTRAINT `fk_movdet_producto` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `facturacion_ruta`;
CREATE TABLE `facturacion_ruta` (
  `ID_FacturaRuta` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `ID_Cliente` int NOT NULL,
  `ID_Asignacion` int NOT NULL,
  `ID_Movimiento` int DEFAULT NULL,
  `Credito_Contado` int DEFAULT NULL,
  `Observacion` text,
  `Saldo_Anterior_Cliente` decimal(10,2) DEFAULT '0.00',
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Estado` enum('Activa','Anulada') NOT NULL DEFAULT 'Activa',
  `ID_Pedido` int DEFAULT NULL,
  PRIMARY KEY (`ID_FacturaRuta`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Asignacion` (`ID_Asignacion`),
  KEY `ID_Movimiento` (`ID_Movimiento`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `ID_Pedido` (`ID_Pedido`),
  CONSTRAINT `facturacion_ruta_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `facturacion_ruta_ibfk_2` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `facturacion_ruta_ibfk_3` FOREIGN KEY (`ID_Movimiento`) REFERENCES `movimientos_ruta_cabecera` (`ID_Movimiento`) ON DELETE SET NULL,
  CONSTRAINT `facturacion_ruta_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `facturacion_ruta_ibfk_5` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `facturacion_ruta_ibfk_6` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `detalle_facturacion_ruta`;
CREATE TABLE `detalle_facturacion_ruta` (
  `ID_DetalleRuta` int NOT NULL AUTO_INCREMENT,
  `ID_FacturaRuta` int DEFAULT NULL,
  `ID_Producto` int DEFAULT NULL,
  `Cantidad` decimal(12,2) DEFAULT NULL,
  `Precio` decimal(12,2) DEFAULT NULL,
  `Costo` decimal(12,2) DEFAULT NULL,
  `Total` decimal(12,2) DEFAULT NULL,
  `ID_Detalle_Movimiento` int DEFAULT NULL,
  PRIMARY KEY (`ID_DetalleRuta`),
  KEY `ID_FacturaRuta` (`ID_FacturaRuta`),
  KEY `ID_Producto` (`ID_Producto`),
  KEY `ID_Detalle_Movimiento` (`ID_Detalle_Movimiento`),
  CONSTRAINT `detalle_facturacion_ruta_ibfk_1` FOREIGN KEY (`ID_FacturaRuta`) REFERENCES `facturacion_ruta` (`ID_FacturaRuta`),
  CONSTRAINT `detalle_facturacion_ruta_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`),
  CONSTRAINT `detalle_facturacion_ruta_ibfk_3` FOREIGN KEY (`ID_Detalle_Movimiento`) REFERENCES `movimientos_ruta_detalle` (`ID_Detalle`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `cuentas_por_cobrar`;
CREATE TABLE `cuentas_por_cobrar` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `ID_Cliente` int NOT NULL,
  `Num_Documento` varchar(255) NOT NULL,
  `Observacion` text,
  `Fecha_Vencimiento` date DEFAULT NULL,
  `Tipo_Movimiento` int NOT NULL,
  `Monto_Movimiento` decimal(12,2) NOT NULL,
  `ID_Empresa` int NOT NULL,
  `Saldo_Pendiente` decimal(12,2) DEFAULT NULL,
  `ID_Factura` int DEFAULT NULL,
  `ID_FacturaRuta` int DEFAULT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Pagada','Anulada','Vencida') DEFAULT 'Pendiente',
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Factura` (`ID_Factura`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `fk_cxc_factura_ruta` (`ID_FacturaRuta`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_3` FOREIGN KEY (`ID_Factura`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_4` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `fk_cxc_factura_ruta` FOREIGN KEY (`ID_FacturaRuta`) REFERENCES `facturacion_ruta` (`ID_FacturaRuta`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `pagos_cuentascobrar`;
CREATE TABLE `pagos_cuentascobrar` (
  `ID_Pago` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int NOT NULL,
  `Fecha` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Monto` decimal(12,2) NOT NULL,
  `ID_MetodoPago` int NOT NULL,
  `Comentarios` text,
  `Detalles_Metodo` text,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Pago`),
  KEY `ID_Movimiento` (`ID_Movimiento`),
  KEY `ID_MetodoPago` (`ID_MetodoPago`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `pagos_cuentascobrar_ibfk_1` FOREIGN KEY (`ID_Movimiento`) REFERENCES `cuentas_por_cobrar` (`ID_Movimiento`) ON DELETE CASCADE,
  CONSTRAINT `pagos_cuentascobrar_ibfk_2` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`),
  CONSTRAINT `pagos_cuentascobrar_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `movimientos_caja_ruta`;
CREATE TABLE `movimientos_caja_ruta` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_Asignacion` int NOT NULL,
  `ID_Usuario` int NOT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `Tipo` enum('APERTURA','VENTA','ABONO','GASTO','CIERRE') NOT NULL,
  `Concepto` varchar(200) NOT NULL,
  `Monto` decimal(12,2) NOT NULL,
  `Tipo_Pago` enum('CONTADO','CREDITO') DEFAULT NULL,
  `ID_FacturaRuta` int DEFAULT NULL,
  `ID_Cliente` int DEFAULT NULL,
  `Saldo_Acumulado` decimal(12,2) DEFAULT NULL,
  `Estado` enum('ACTIVO','ANULADO') DEFAULT 'ACTIVO',
  `ID_MetodoPago` int DEFAULT NULL,
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Asignacion` (`ID_Asignacion`),
  KEY `ID_Usuario` (`ID_Usuario`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `idx_fecha_usuario` (`Fecha`,`ID_Usuario`),
  KEY `idx_fecha_ruta` (`Fecha`,`ID_Asignacion`),
  KEY `ID_MetodoPago` (`ID_MetodoPago`),
  CONSTRAINT `movimientos_caja_ruta_ibfk_1` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `movimientos_caja_ruta_ibfk_2` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `movimientos_caja_ruta_ibfk_3` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `abonos_detalle`;
CREATE TABLE `abonos_detalle` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento_Caja` int DEFAULT NULL,
  `ID_Asignacion` int NOT NULL,
  `ID_Usuario` int NOT NULL,
  `ID_Cliente` int NOT NULL,
  `ID_CuentaCobrar` int NOT NULL,
  `Monto_Aplicado` decimal(12,2) NOT NULL,
  `Saldo_Anterior` decimal(12,2) NOT NULL,
  `Saldo_Nuevo` decimal(12,2) NOT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_MetodoPago` int DEFAULT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Movimiento_Caja` (`ID_Movimiento_Caja`),
  KEY `ID_Asignacion` (`ID_Asignacion`),
  KEY `ID_Usuario` (`ID_Usuario`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_CuentaCobrar` (`ID_CuentaCobrar`),
  KEY `idx_fecha_usuario_ruta` (`Fecha`,`ID_Usuario`,`ID_Asignacion`),
  KEY `fk_abono_metodo_pago` (`ID_MetodoPago`),
  CONSTRAINT `abonos_detalle_ibfk_2` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `abonos_detalle_ibfk_3` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `abonos_detalle_ibfk_4` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `abonos_detalle_ibfk_5` FOREIGN KEY (`ID_CuentaCobrar`) REFERENCES `cuentas_por_cobrar` (`ID_Movimiento`),
  CONSTRAINT `fk_abono_metodo_pago` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `abonos_general`;
CREATE TABLE `abonos_general` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int NOT NULL,
  `ID_Cliente` int NOT NULL,
  `ID_CuentaCobrar` int NOT NULL,
  `Monto_Aplicado` decimal(12,2) NOT NULL,
  `Saldo_Anterior` decimal(12,2) NOT NULL,
  `Saldo_Nuevo` decimal(12,2) NOT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_MetodoPago` int DEFAULT NULL,
  `caja_movimientos` varchar(100) NOT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Usuario` (`ID_Usuario`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_CuentaCobrar` (`ID_CuentaCobrar`),
  KEY `fk_abono_general_metodo_pago` (`ID_MetodoPago`),
  CONSTRAINT `abonos_general_ibfk_3` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `abonos_general_ibfk_4` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `abonos_general_ibfk_5` FOREIGN KEY (`ID_CuentaCobrar`) REFERENCES `cuentas_por_cobrar` (`ID_Movimiento`),
  CONSTRAINT `abonos_general_ibfk_6` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `anticipos_clientes`;
CREATE TABLE `anticipos_clientes` (
  `ID_Anticipo` int NOT NULL AUTO_INCREMENT,
  `ID_Cliente` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Cajas` int NOT NULL,
  `Cajas_Consumidas` int NOT NULL DEFAULT '0',
  `Precio_Unitario` decimal(10,2) DEFAULT NULL,
  `Monto_Pagado` decimal(12,2) NOT NULL,
  `Saldo_Restante` decimal(12,2) NOT NULL,
  `Fecha_Anticipo` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Vencimiento` datetime DEFAULT NULL,
  `Estado` enum('ACTIVO','COMPLETADO','CANCELADO') DEFAULT 'ACTIVO',
  `Notas` text,
  PRIMARY KEY (`ID_Anticipo`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `anticipos_clientes_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `anticipos_clientes_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `entregas`;
CREATE TABLE `entregas` (
  `ID_Entrega` int NOT NULL AUTO_INCREMENT,
  `ID_Cliente` int NOT NULL,
  `ID_Sucursal` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Cajas` int NOT NULL,
  `Precio_Unitario` decimal(12,2) NOT NULL,
  `Total` decimal(12,2) NOT NULL,
  `Usa_Anticipo` tinyint(1) NOT NULL DEFAULT '0',
  `ID_Anticipo` int DEFAULT NULL,
  `Fecha_Entrega` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario` int DEFAULT NULL,
  `Notas` text,
  PRIMARY KEY (`ID_Entrega`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Sucursal` (`ID_Sucursal`),
  KEY `ID_Producto` (`ID_Producto`),
  KEY `idx_entregas_fecha` (`Fecha_Entrega` DESC),
  KEY `idx_entregas_anticipo` (`ID_Anticipo`),
  CONSTRAINT `entregas_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `entregas_ibfk_2` FOREIGN KEY (`ID_Sucursal`) REFERENCES `sucursales` (`ID_Sucursal`),
  CONSTRAINT `entregas_ibfk_3` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `detalle_entregas`;
CREATE TABLE `detalle_entregas` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Entrega` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Cajas` int NOT NULL,
  `Precio_Unitario` decimal(12,2) NOT NULL,
  `Total` decimal(12,2) NOT NULL,
  `Usa_Anticipo` tinyint(1) NOT NULL DEFAULT '0',
  `ID_Anticipo` int DEFAULT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Entrega` (`ID_Entrega`),
  KEY `ID_Producto` (`ID_Producto`),
  KEY `ID_Anticipo` (`ID_Anticipo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `movimientos_inventario`;
CREATE TABLE `movimientos_inventario` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_TipoMovimiento` int NOT NULL,
  `N_Factura_Externa` varchar(255) DEFAULT NULL,
  `ID_Factura_Venta` int DEFAULT NULL,
  `Fecha` date NOT NULL,
  `ID_Proveedor` int DEFAULT NULL,
  `Tipo_Compra` enum('CONTADO','CREDITO') DEFAULT NULL,
  `Observacion` text,
  `ID_Empresa` int NOT NULL,
  `ID_Bodega` int NOT NULL,
  `ID_Bodega_Destino` int DEFAULT NULL,
  `ID_Pedido_Origen` int DEFAULT NULL,
  `UbicacionEntrega` text,
  `ID_Usuario_Creacion` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Modificacion` datetime DEFAULT NULL,
  `ID_Usuario_Modificacion` int DEFAULT NULL,
  `Estado` enum('Activa','Anulada','Pendiente','Cancelada') DEFAULT 'Activa',
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Bodega_Destino` (`ID_Bodega_Destino`),
  KEY `ID_Usuario_Modificacion` (`ID_Usuario_Modificacion`),
  KEY `idx_fecha` (`Fecha`),
  KEY `idx_tipo_movimiento` (`ID_TipoMovimiento`),
  KEY `idx_bodega` (`ID_Bodega`),
  KEY `idx_proveedor` (`ID_Proveedor`),
  KEY `idx_tipo_compra` (`Tipo_Compra`),
  KEY `idx_factura_venta` (`ID_Factura_Venta`),
  KEY `idx_usuario_creacion` (`ID_Usuario_Creacion`),
  KEY `idx_entradas_busqueda` (`ID_TipoMovimiento`,`Fecha`,`Estado`,`ID_Proveedor`,`ID_Bodega`),
  KEY `idx_pedido_origen` (`ID_Pedido_Origen`),
  CONSTRAINT `fk_movinv_pedido` FOREIGN KEY (`ID_Pedido_Origen`) REFERENCES `pedidos` (`ID_Pedido`) ON DELETE SET NULL,
  CONSTRAINT `movimientos_inventario_ibfk_1` FOREIGN KEY (`ID_TipoMovimiento`) REFERENCES `catalogo_movimientos` (`ID_TipoMovimiento`),
  CONSTRAINT `movimientos_inventario_ibfk_2` FOREIGN KEY (`ID_Factura_Venta`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `movimientos_inventario_ibfk_3` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `movimientos_inventario_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `movimientos_inventario_ibfk_5` FOREIGN KEY (`ID_Bodega`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_6` FOREIGN KEY (`ID_Bodega_Destino`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_7` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `movimientos_inventario_ibfk_8` FOREIGN KEY (`ID_Usuario_Modificacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `detalle_movimientos_inventario`;
CREATE TABLE `detalle_movimientos_inventario` (
  `ID_Detalle_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad` decimal(15,2) NOT NULL DEFAULT '0.00',
  `Costo_Unitario` decimal(15,2) DEFAULT '0.00',
  `Precio_Unitario` decimal(15,2) DEFAULT '0.00',
  `Subtotal` decimal(15,2) DEFAULT '0.00',
  `ID_Usuario_Creacion` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Detalle_Movimiento`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_movimiento` (`ID_Movimiento`),
  KEY `idx_producto` (`ID_Producto`),
  CONSTRAINT `detalle_movimientos_inventario_ibfk_1` FOREIGN KEY (`ID_Movimiento`) REFERENCES `movimientos_inventario` (`ID_Movimiento`) ON DELETE CASCADE,
  CONSTRAINT `detalle_movimientos_inventario_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`),
  CONSTRAINT `detalle_movimientos_inventario_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `inventario_bodega`;
CREATE TABLE `inventario_bodega` (
  `ID_Bodega` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Existencias` decimal(12,2) DEFAULT '0.00',
  PRIMARY KEY (`ID_Bodega`,`ID_Producto`),
  UNIQUE KEY `idx_unico_producto_bodega` (`ID_Producto`,`ID_Bodega`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `inventario_bodega_ibfk_1` FOREIGN KEY (`ID_Bodega`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `inventario_bodega_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `inventario_ruta`;
CREATE TABLE `inventario_ruta` (
  `ID_Inventario_Ruta` int NOT NULL AUTO_INCREMENT,
  `ID_Asignacion` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Fecha_Actualizacion` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Inventario_Ruta`),
  UNIQUE KEY `uk_producto_asignacion` (`ID_Asignacion`,`ID_Producto`),
  KEY `idx_producto` (`ID_Producto`),
  KEY `idx_asignacion` (`ID_Asignacion`),
  CONSTRAINT `fk_inv_ruta_asignacion` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`) ON DELETE CASCADE,
  CONSTRAINT `fk_inv_ruta_producto` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `cuentas_por_pagar`;
CREATE TABLE `cuentas_por_pagar` (
  `ID_Cuenta` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int DEFAULT NULL,
  `Fecha` date DEFAULT NULL,
  `ID_Proveedor` int DEFAULT NULL,
  `Num_Documento` varchar(255) DEFAULT NULL,
  `Observacion` text,
  `Fecha_Vencimiento` date DEFAULT NULL,
  `Tipo_Movimiento` int DEFAULT NULL,
  `Monto_Movimiento` decimal(12,2) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Saldo_Pendiente` decimal(12,2) DEFAULT '0.00',
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Pagada','Anulada','Vencida','Parcial') DEFAULT 'Pendiente',
  PRIMARY KEY (`ID_Cuenta`),
  KEY `ID_Proveedor` (`ID_Proveedor`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `cuentas_por_pagar_ibfk_1` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `cuentas_por_pagar_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `cuentas_por_pagar_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `pagos_cuentaspagar`;
CREATE TABLE `pagos_cuentaspagar` (
  `ID_Pago` int NOT NULL AUTO_INCREMENT,
  `ID_Cuenta` int DEFAULT NULL,
  `Fecha` datetime DEFAULT NULL,
  `Monto` decimal(12,2) DEFAULT NULL,
  `ID_MetodoPago` int DEFAULT NULL,
  `Detalles_Metodo` text,
  `Comentarios` text,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Pago`),
  KEY `ID_Cuenta` (`ID_Cuenta`),
  KEY `ID_MetodoPago` (`ID_MetodoPago`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `pagos_cuentaspagar_ibfk_1` FOREIGN KEY (`ID_Cuenta`) REFERENCES `cuentas_por_pagar` (`ID_Cuenta`),
  CONSTRAINT `pagos_cuentaspagar_ibfk_2` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`),
  CONSTRAINT `pagos_cuentaspagar_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `abonos_proveedores_detalle`;
CREATE TABLE `abonos_proveedores_detalle` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int NOT NULL,
  `ID_Proveedor` int NOT NULL,
  `ID_CuentaPagar` int NOT NULL,
  `Monto_Aplicado` decimal(12,2) NOT NULL,
  `Saldo_Anterior` decimal(12,2) NOT NULL,
  `Saldo_Nuevo` decimal(12,2) NOT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_MetodoPago` int DEFAULT NULL,
  `Detalles_Metodo` text,
  `Comentarios` text,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Usuario` (`ID_Usuario`),
  KEY `ID_Proveedor` (`ID_Proveedor`),
  KEY `ID_CuentaPagar` (`ID_CuentaPagar`),
  KEY `fk_abono_prov_metodo` (`ID_MetodoPago`),
  CONSTRAINT `abonos_prov_detalle_ibfk_2` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `abonos_prov_detalle_ibfk_3` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `abonos_prov_detalle_ibfk_4` FOREIGN KEY (`ID_CuentaPagar`) REFERENCES `cuentas_por_pagar` (`ID_Cuenta`),
  CONSTRAINT `fk_abono_prov_metodo` FOREIGN KEY (`ID_MetodoPago`) REFERENCES `metodos_pago` (`ID_MetodoPago`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `cargas_pendientes_recepcion`;
CREATE TABLE `cargas_pendientes_recepcion` (
  `ID_Carga` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int NOT NULL,
  `ID_Proveedor` int NOT NULL,
  `Num_Factura` varchar(255) NOT NULL,
  `Fecha_Carga` date NOT NULL,
  `ID_Usuario_Carga` int NOT NULL,
  `Estado` enum('PENDIENTE','RECIBIDA_PARCIAL','RECIBIDA_TOTAL','RECHAZADA') DEFAULT 'PENDIENTE',
  `Observaciones` text,
  `Fecha_Recepcion` date DEFAULT NULL,
  `ID_Usuario_Recepcion` int DEFAULT NULL,
  `factura_ruta` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`ID_Carga`),
  KEY `ID_Movimiento` (`ID_Movimiento`),
  KEY `ID_Proveedor` (`ID_Proveedor`),
  KEY `ID_Usuario_Carga` (`ID_Usuario_Carga`),
  KEY `ID_Usuario_Recepcion` (`ID_Usuario_Recepcion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `cargas_pendientes_detalle`;
CREATE TABLE `cargas_pendientes_detalle` (
  `ID_Detalle` int NOT NULL AUTO_INCREMENT,
  `ID_Carga` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Cargada` decimal(12,2) NOT NULL,
  `Cantidad_Recibida` decimal(12,2) DEFAULT '0.00',
  `Costo_Unitario` decimal(12,2) NOT NULL,
  PRIMARY KEY (`ID_Detalle`),
  KEY `ID_Carga` (`ID_Carga`),
  KEY `ID_Producto` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `gastos_generales`;
CREATE TABLE `gastos_generales` (
  `ID_Gasto` int NOT NULL AUTO_INCREMENT,
  `ID_Tipo_Gasto` int NOT NULL,
  `ID_Subcategoria` int DEFAULT NULL,
  `Fecha` date NOT NULL,
  `Monto` decimal(12,2) NOT NULL,
  `Descripcion` text,
  `N_Factura` varchar(50) DEFAULT NULL,
  `ID_Proveedor` int DEFAULT NULL,
  `ID_Vehiculo` int DEFAULT NULL,
  `Metodo_Pago` enum('EFECTIVO','TRANSFERENCIA','TARJETA','CHEQUE') DEFAULT 'EFECTIVO',
  `Comprobante` varchar(255) DEFAULT NULL,
  `ID_Empresa` int NOT NULL,
  `Estado` enum('Activo','Anulado') DEFAULT 'Activo',
  `Fecha_Registro` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Registro` int DEFAULT NULL,
  PRIMARY KEY (`ID_Gasto`),
  KEY `ID_Tipo_Gasto` (`ID_Tipo_Gasto`),
  KEY `ID_Subcategoria` (`ID_Subcategoria`),
  KEY `ID_Proveedor` (`ID_Proveedor`),
  KEY `ID_Vehiculo` (`ID_Vehiculo`),
  CONSTRAINT `fk_gastos_subcategoria` FOREIGN KEY (`ID_Subcategoria`) REFERENCES `subcategorias_gasto` (`ID_Subcategoria`),
  CONSTRAINT `fk_gastos_tipo` FOREIGN KEY (`ID_Tipo_Gasto`) REFERENCES `tipos_gasto` (`ID_Tipo_Gasto`),
  CONSTRAINT `fk_gastos_vehiculo` FOREIGN KEY (`ID_Vehiculo`) REFERENCES `vehiculos` (`ID_Vehiculo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `gastos_vehiculo_detalle`;
CREATE TABLE `gastos_vehiculo_detalle` (
  `ID_Gasto_Vehiculo` int NOT NULL AUTO_INCREMENT,
  `ID_Gasto` int NOT NULL,
  `ID_Vehiculo` int NOT NULL,
  `Kilometraje` int DEFAULT NULL,
  `Tipo_Mantenimiento` varchar(50) DEFAULT NULL,
  `Taller` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`ID_Gasto_Vehiculo`),
  KEY `ID_Gasto` (`ID_Gasto`),
  CONSTRAINT `fk_gasto_vehiculo_gasto` FOREIGN KEY (`ID_Gasto`) REFERENCES `gastos_generales` (`ID_Gasto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `caja_movimientos`;
CREATE TABLE `caja_movimientos` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `Tipo_Movimiento` enum('ENTRADA','SALIDA') NOT NULL,
  `Descripcion` varchar(500) NOT NULL,
  `Monto` decimal(15,2) NOT NULL,
  `ID_Factura` int DEFAULT NULL,
  `ID_Pagos_cxc` int DEFAULT NULL,
  `ID_Usuario` int DEFAULT NULL,
  `Referencia_Documento` varchar(100) DEFAULT NULL,
  `Es_Ajuste` tinyint(1) DEFAULT '0',
  `Movimiento_Origen` int DEFAULT NULL,
  `Comentario_Ajuste` varchar(500) DEFAULT NULL,
  `Estado` enum('ACTIVO','ANULADO') DEFAULT 'ACTIVO',
  `Fecha_Anulacion` datetime DEFAULT NULL,
  `ID_Usuario_Anula` int DEFAULT NULL,
  PRIMARY KEY (`ID_Movimiento`),
  KEY `idx_es_ajuste` (`Es_Ajuste`),
  KEY `idx_movimiento_origen` (`Movimiento_Origen`),
  KEY `idx_estado_fecha` (`Estado`,`Fecha`),
  KEY `idx_fecha_estado_tipo` (`Fecha`,`Estado`,`Tipo_Movimiento`),
  CONSTRAINT `caja_movimientos_chk_1` CHECK ((`Monto` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `bitacora`;
CREATE TABLE `bitacora` (
  `ID_Bitacora` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int DEFAULT NULL,
  `Fecha` datetime DEFAULT CURRENT_TIMESTAMP,
  `Modulo` varchar(255) DEFAULT NULL,
  `Accion` varchar(255) DEFAULT NULL,
  `IP_Acceso` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`ID_Bitacora`),
  KEY `ID_Usuario` (`ID_Usuario`),
  CONSTRAINT `bitacora_ibfk_1` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `log_anulaciones`;
CREATE TABLE `log_anulaciones` (
  `ID_Log` int NOT NULL AUTO_INCREMENT,
  `ID_Factura` int NOT NULL,
  `Tipo` enum('ruta','local') COLLATE utf8mb4_unicode_ci NOT NULL,
  `Motivo` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `ID_Usuario_Anula` int NOT NULL,
  `Fecha_Anulacion` datetime NOT NULL,
  `ID_Empresa` int NOT NULL,
  PRIMARY KEY (`ID_Log`),
  KEY `ID_Usuario_Anula` (`ID_Usuario_Anula`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `idx_factura_tipo` (`ID_Factura`,`Tipo`),
  CONSTRAINT `log_anulaciones_ibfk_1` FOREIGN KEY (`ID_Usuario_Anula`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `log_anulaciones_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `log_cambios_visibilidad`;
CREATE TABLE `log_cambios_visibilidad` (
  `ID_Log` int NOT NULL AUTO_INCREMENT,
  `fecha_cambio` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario` int NOT NULL,
  `tipo_cliente` enum('Comun','Especial') NOT NULL,
  `ID_Categoria` int NOT NULL,
  `valor_anterior` tinyint(1) DEFAULT NULL,
  `valor_nuevo` tinyint(1) DEFAULT NULL,
  `accion` enum('INSERT','UPDATE','DELETE') DEFAULT 'UPDATE',
  PRIMARY KEY (`ID_Log`),
  KEY `ID_Usuario` (`ID_Usuario`),
  KEY `fecha_cambio` (`fecha_cambio`),
  CONSTRAINT `fk_log_usuario` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------
-- 3. VISTAS DEL SISTEMA
-- --------------------------------------------------------

DROP VIEW IF EXISTS `vista_gastos_unificados`;
CREATE VIEW `vista_gastos_unificados` AS 
SELECT 
    'INVENTARIO' AS `origen`,
    `cp`.`ID_Categoria` AS `id_tipo`,
    `cp`.`Descripcion` AS `tipo_gasto`,
    NULL AS `subcategoria`,
    `mi`.`Fecha` AS `Fecha`,
    COALESCE(SUM((`dmi`.`Cantidad` * `dmi`.`Costo_Unitario`)), 0) AS `monto`,
    `mi`.`N_Factura_Externa` AS `factura`,
    `pr`.`Nombre` AS `proveedor`,
    `pr`.`ID_Proveedor` AS `id_proveedor`,
    NULL AS `vehiculo`,
    `mi`.`ID_Empresa` AS `ID_Empresa`,
    `mi`.`Estado` AS `Estado`,
    `mi`.`ID_Movimiento` AS `id_gasto`,
    NULL AS `id_categoria_inv`
FROM `movimientos_inventario` `mi`
JOIN `detalle_movimientos_inventario` `dmi` ON `mi`.`ID_Movimiento` = `dmi`.`ID_Movimiento`
JOIN `productos` `p` ON `dmi`.`ID_Producto` = `p`.`ID_Producto`
JOIN `categorias_producto` `cp` ON `p`.`ID_Categoria` = `cp`.`ID_Categoria`
LEFT JOIN `proveedores` `pr` ON `mi`.`ID_Proveedor` = `pr`.`ID_Proveedor`
WHERE `mi`.`ID_TipoMovimiento` = 1 AND `mi`.`Estado` = 'Activa'
GROUP BY `cp`.`ID_Categoria`, `cp`.`Descripcion`, `mi`.`Fecha`, `mi`.`N_Factura_Externa`, `pr`.`Nombre`, `pr`.`ID_Proveedor`, `mi`.`ID_Empresa`, `mi`.`Estado`, `mi`.`ID_Movimiento`

UNION ALL

SELECT 
    'GASTO_DIRECTO' AS `origen`,
    `tg`.`ID_Tipo_Gasto` AS `id_tipo`,
    `tg`.`Nombre` AS `tipo_gasto`,
    `sg`.`Nombre` AS `subcategoria`,
    `gg`.`Fecha` AS `Fecha`,
    COALESCE(`gg`.`Monto`, 0) AS `monto`,
    `gg`.`N_Factura` AS `factura`,
    `pr`.`Nombre` AS `proveedor`,
    `pr`.`ID_Proveedor` AS `id_proveedor`,
    `v`.`Placa` AS `vehiculo`,
    `gg`.`ID_Empresa` AS `ID_Empresa`,
    `gg`.`Estado` AS `Estado`,
    `gg`.`ID_Gasto` AS `id_gasto`,
    NULL AS `id_categoria_inv`
FROM `gastos_generales` `gg`
JOIN `tipos_gasto` `tg` ON `gg`.`ID_Tipo_Gasto` = `tg`.`ID_Tipo_Gasto`
LEFT JOIN `subcategorias_gasto` `sg` ON `gg`.`ID_Subcategoria` = `sg`.`ID_Subcategoria`
LEFT JOIN `proveedores` `pr` ON `gg`.`ID_Proveedor` = `pr`.`ID_Proveedor`
LEFT JOIN `vehiculos` `v` ON `gg`.`ID_Vehiculo` = `v`.`ID_Vehiculo`
WHERE `gg`.`Estado` = 'Activo';

DROP VIEW IF EXISTS `vista_kardex_productos`;
CREATE VIEW `vista_kardex_productos` AS 
SELECT 
    `p`.`ID_Producto` AS `ID_Producto`,
    `p`.`COD_Producto` AS `COD_Producto`,
    `p`.`Descripcion` AS `Producto`,
    `c`.`Descripcion` AS `Categoria`,
    `u`.`Descripcion` AS `Unidad_Medida`,
    `u`.`Abreviatura` AS `Abreviatura`,
    `b`.`Nombre` AS `Bodega`,
    COALESCE(`ib`.`Existencias`, 0) AS `Stock_Actual`,
    `p`.`Stock_Minimo` AS `Stock_Minimo`,
    0 AS `Salidas_Mes`,
    0 AS `Entradas_Mes`
FROM `productos` `p`
LEFT JOIN `categorias_producto` `c` ON `p`.`ID_Categoria` = `c`.`ID_Categoria`
LEFT JOIN `unidades_medida` `u` ON `p`.`Unidad_Medida` = `u`.`ID_Unidad`
LEFT JOIN `inventario_bodega` `ib` ON `p`.`ID_Producto` = `ib`.`ID_Producto`
LEFT JOIN `bodegas` `b` ON `ib`.`ID_Bodega` = `b`.`ID_Bodega`;

DROP VIEW IF EXISTS `vw_entradas_inventario`;
CREATE VIEW `vw_entradas_inventario` AS 
SELECT 
    `mi`.`ID_Movimiento` AS `ID_Movimiento`,
    `mi`.`Fecha` AS `Fecha`,
    `mi`.`ID_TipoMovimiento` AS `ID_TipoMovimiento`,
    `cm`.`Descripcion` AS `Tipo_Movimiento`,
    `cm`.`Letra` AS `Letra`,
    `mi`.`N_Factura_Externa` AS `N_Factura_Externa`,
    `mi`.`ID_Proveedor` AS `ID_Proveedor`,
    `pr`.`Nombre` AS `Proveedor`,
    `mi`.`Tipo_Compra` AS `Tipo_Compra`,
    `mi`.`ID_Bodega` AS `ID_Bodega`,
    `b`.`Nombre` AS `Bodega`,
    `p`.`ID_Producto` AS `ID_Producto`,
    `p`.`COD_Producto` AS `Codigo_Producto`,
    `p`.`Descripcion` AS `Producto`,
    `dmi`.`Cantidad` AS `Cantidad`,
    `dmi`.`Costo_Unitario` AS `Costo_Unitario`,
    `dmi`.`Precio_Unitario` AS `Precio_Unitario`,
    `dmi`.`Subtotal` AS `Subtotal`,
    `mi`.`Estado` AS `Estado`
FROM `movimientos_inventario` `mi`
JOIN `catalogo_movimientos` `cm` ON `mi`.`ID_TipoMovimiento` = `cm`.`ID_TipoMovimiento`
LEFT JOIN `proveedores` `pr` ON `mi`.`ID_Proveedor` = `pr`.`ID_Proveedor`
LEFT JOIN `bodegas` `b` ON `mi`.`ID_Bodega` = `b`.`ID_Bodega`
LEFT JOIN `detalle_movimientos_inventario` `dmi` ON `mi`.`ID_Movimiento` = `dmi`.`ID_Movimiento`
LEFT JOIN `productos` `p` ON `dmi`.`ID_Producto` = `p`.`ID_Producto`;

SET FOREIGN_KEY_CHECKS = 1;
