
CREATE TABLE `asignacion_vendedores` (
  `ID_Asignacion` int NOT NULL AUTO_INCREMENT,
  `ID_Usuario` int NOT NULL COMMENT 'Vendedor',
  `ID_Ruta` int NOT NULL,
  `ID_Vehiculo` int DEFAULT NULL,
  `Fecha_Asignacion` date NOT NULL,
  `Fecha_Finalizacion` date DEFAULT NULL,
  `Estado` enum('Activa','Finalizada','Suspendida') DEFAULT 'Activa',
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Asigna` int DEFAULT NULL COMMENT 'Quién hace la asignación',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Hora_Inicio` time DEFAULT NULL,
  `Hora_Fin` time DEFAULT NULL,
  PRIMARY KEY (`ID_Asignacion`),
  UNIQUE KEY `uc_vendedor_fecha` (`ID_Usuario`,`Fecha_Asignacion`),
  KEY `ID_Ruta` (`ID_Ruta`),
  KEY `ID_Vehiculo` (`ID_Vehiculo`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Asigna` (`ID_Usuario_Asigna`),
  CONSTRAINT `asignacion_vendedores_ibfk_1` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `asignacion_vendedores_ibfk_2` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`),
  CONSTRAINT `asignacion_vendedores_ibfk_3` FOREIGN KEY (`ID_Vehiculo`) REFERENCES `vehiculos` (`ID_Vehiculo`),
  CONSTRAINT `asignacion_vendedores_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `asignacion_vendedores_ibfk_5` FOREIGN KEY (`ID_Usuario_Asigna`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=6859 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=162 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `catalogo_movimientos` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `clientes` (
  `ID_Cliente` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `ID_Ruta` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `tipo_cliente` enum('Comun','Especial') NOT NULL DEFAULT 'Comun',
  PRIMARY KEY (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_clientes_busqueda` (`ID_Empresa`,`Estado`,`Nombre`),
  KEY `idx_clientes_ruc_empresa` (`RUC_CEDULA`,`ID_Empresa`),
  KEY `idx_clientes_telefono` (`Telefono`),
  KEY `idx_clientes_tipo` (`tipo_cliente`,`Estado`),
  KEY `idx_clientes_fecha_creacion` (`Fecha_Creacion` DESC),
  KEY `idx_clientes_ruta` (`ID_Ruta`),
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `clientes_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `clientes_ibfk_ruta` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `config_visibilidad_categorias` (
  `ID_Config` int NOT NULL AUTO_INCREMENT,
  `tipo_cliente` enum('Comun','Especial') NOT NULL,
  `ID_Categoria` int NOT NULL,
  `visible` tinyint(1) DEFAULT '0' COMMENT '1 = visible, 0 = no visible',
  `fecha_creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Config`),
  UNIQUE KEY `unico_tipo_categoria` (`tipo_cliente`,`ID_Categoria`),
  KEY `ID_Categoria` (`ID_Categoria`),
  CONSTRAINT `fk_config_categoria` FOREIGN KEY (`ID_Categoria`) REFERENCES `categorias_producto` (`ID_Categoria`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=146 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Pagada','Anulada','Vencida') DEFAULT 'Pendiente' COMMENT 'Estados: Pendiente, Pagada, Anulada, Vencida',
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Factura` (`ID_Factura`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_3` FOREIGN KEY (`ID_Factura`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_4` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=232 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=326 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `facturacion` (
  `ID_Factura` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `IDCliente` int NOT NULL,
  `Credito_Contado` int DEFAULT NULL,
  `Observacion` text,
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Estado` enum('Activa','Anulada') NOT NULL DEFAULT 'Activa',
  `ID_Pedido` int DEFAULT NULL,
  PRIMARY KEY (`ID_Factura`),
  KEY `IDCliente` (`IDCliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_facturacion_pedido` (`ID_Pedido`),
  CONSTRAINT `facturacion_ibfk_1` FOREIGN KEY (`IDCliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `facturacion_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `facturacion_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `fk_facturacion_pedido` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`)
) ENGINE=InnoDB AUTO_INCREMENT=176 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
  `UbicacionEntrega` text,
  `ID_Usuario_Creacion` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Modificacion` datetime DEFAULT NULL,
  `ID_Usuario_Modificacion` int DEFAULT NULL,
  `Estado` enum('Activa','Anulada') NOT NULL DEFAULT 'Activa',
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
  CONSTRAINT `movimientos_inventario_ibfk_1` FOREIGN KEY (`ID_TipoMovimiento`) REFERENCES `catalogo_movimientos` (`ID_TipoMovimiento`),
  CONSTRAINT `movimientos_inventario_ibfk_2` FOREIGN KEY (`ID_Factura_Venta`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `movimientos_inventario_ibfk_3` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `movimientos_inventario_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `movimientos_inventario_ibfk_5` FOREIGN KEY (`ID_Bodega`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_6` FOREIGN KEY (`ID_Bodega_Destino`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_7` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `movimientos_inventario_ibfk_8` FOREIGN KEY (`ID_Usuario_Modificacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=272 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=28 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `pedidos` (
  `ID_Pedido` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `ID_Cliente` int NOT NULL,
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Aprobado','Entregado','Cancelado') DEFAULT 'Pendiente',
  `Observacion` text,
  `Tipo_Entrega` enum('Retiro en local','Entrega a domicilio') DEFAULT 'Retiro en local',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Prioridad` enum('Urgente','Normal','Bajo') NOT NULL DEFAULT 'Normal',
  PRIMARY KEY (`ID_Pedido`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `pedidos_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `pedidos_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `pedidos_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `productos` (
  `ID_Producto` int NOT NULL AUTO_INCREMENT,
  `COD_Producto` varchar(100) DEFAULT NULL,
  `Descripcion` varchar(255) NOT NULL,
  `Unidad_Medida` int DEFAULT NULL,
  `Estado` enum('activo','inactivo') DEFAULT 'activo',
  `ID_Categoria` int DEFAULT NULL,
  `Precio_Venta` decimal(12,2) DEFAULT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `proveedores` (
  `ID_Proveedor` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Estado` enum('ACTIVO','INACTIVO') DEFAULT 'ACTIVO',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Proveedor`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `proveedores_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `proveedores_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  `Estado` enum('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`),
  UNIQUE KEY `uc_descripcion` (`Descripcion`),
  UNIQUE KEY `uc_abreviatura` (`Abreviatura`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `vehiculos` (
  `ID_Vehiculo` int NOT NULL AUTO_INCREMENT,
  `Placa` varchar(20) NOT NULL,
  `Marca` varchar(100) DEFAULT NULL,
  `Modelo` varchar(100) DEFAULT NULL,
  `Anio` year DEFAULT NULL,
  `Estado` enum('Disponible','En Ruta','Mantenimiento','Inactivo') DEFAULT 'Disponible',
  `ID_Empresa` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Vencimiento_Seguro` date DEFAULT NULL COMMENT 'Fecha de vencimiento del seguro del vehículo',
  `Tipo_Combustible` enum('Gasolina','Diesel') NOT NULL DEFAULT 'Gasolina',
  PRIMARY KEY (`ID_Vehiculo`),
  UNIQUE KEY `uc_placa_empresa` (`Placa`,`ID_Empresa`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `vehiculos_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


--
-- Temporary view structure for view `vista_kardex_productos`
--

DROP TABLE IF EXISTS `vista_kardex_productos`;
/*!50001 DROP VIEW IF EXISTS `vista_kardex_productos`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `vista_kardex_productos` AS SELECT 
 1 AS `ID_Producto`,
 1 AS `COD_Producto`,
 1 AS `Producto`,
 1 AS `Categoria`,
 1 AS `Unidad_Medida`,
 1 AS `Abreviatura`,
 1 AS `Bodega`,
 1 AS `Stock_Actual`,
 1 AS `Stock_Minimo`,
 1 AS `Salidas_Mes`,
 1 AS `Entradas_Mes`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `vw_entradas_inventario`
--

DROP TABLE IF EXISTS `vw_entradas_inventario`;
/*!50001 DROP VIEW IF EXISTS `vw_entradas_inventario`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `vw_entradas_inventario` AS SELECT 
 1 AS `ID_Movimiento`,
 1 AS `Fecha`,
 1 AS `ID_TipoMovimiento`,
 1 AS `Tipo_Movimiento`,
 1 AS `Letra`,
 1 AS `N_Factura_Externa`,
 1 AS `ID_Proveedor`,
 1 AS `Proveedor`,
 1 AS `Tipo_Compra`,
 1 AS `ID_Bodega`,
 1 AS `Bodega`,
 1 AS `ID_Producto`,
 1 AS `Codigo_Producto`,
 1 AS `Producto`,
 1 AS `Cantidad`,
 1 AS `Costo_Unitario`,
 1 AS `Precio_Unitario`,
 1 AS `Subtotal`,
 1 AS `Estado`*/;
SET character_set_client = @saved_cs_client;

--
-- Dumping events for database 'db_ferdel'
--

--
-- Dumping routines for database 'db_ferdel'
--

--
-- Final view structure for view `vista_kardex_productos`
--

/*!50001 DROP VIEW IF EXISTS `vista_kardex_productos`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `vista_kardex_productos` AS select `p`.`ID_Producto` AS `ID_Producto`,`p`.`COD_Producto` AS `COD_Producto`,`p`.`Descripcion` AS `Producto`,`cp`.`Descripcion` AS `Categoria`,`um`.`Descripcion` AS `Unidad_Medida`,`um`.`Abreviatura` AS `Abreviatura`,`b`.`Nombre` AS `Bodega`,`ib`.`Existencias` AS `Stock_Actual`,`p`.`Stock_Minimo` AS `Stock_Minimo`,(select sum(`dmi2`.`Cantidad`) from ((`detalle_movimientos_inventario` `dmi2` join `movimientos_inventario` `mi2` on((`dmi2`.`ID_Movimiento` = `mi2`.`ID_Movimiento`))) join `catalogo_movimientos` `cm2` on((`mi2`.`ID_TipoMovimiento` = `cm2`.`ID_TipoMovimiento`))) where ((`dmi2`.`ID_Producto` = `p`.`ID_Producto`) and (`mi2`.`Estado` = 'Activa') and (`mi2`.`ID_Bodega` = `b`.`ID_Bodega`) and ((`cm2`.`Adicion` = 'RESTA') or (`cm2`.`Letra` = 'S')) and (month(`mi2`.`Fecha`) = month(curdate())) and (year(`mi2`.`Fecha`) = year(curdate())))) AS `Salidas_Mes`,(select sum(`dmi2`.`Cantidad`) from ((`detalle_movimientos_inventario` `dmi2` join `movimientos_inventario` `mi2` on((`dmi2`.`ID_Movimiento` = `mi2`.`ID_Movimiento`))) join `catalogo_movimientos` `cm2` on((`mi2`.`ID_TipoMovimiento` = `cm2`.`ID_TipoMovimiento`))) where ((`dmi2`.`ID_Producto` = `p`.`ID_Producto`) and (`mi2`.`Estado` = 'Activa') and (`mi2`.`ID_Bodega` = `b`.`ID_Bodega`) and (`cm2`.`Letra` = 'E') and (month(`mi2`.`Fecha`) = month(curdate())) and (year(`mi2`.`Fecha`) = year(curdate())))) AS `Entradas_Mes` from ((((`productos` `p` join `categorias_producto` `cp` on((`p`.`ID_Categoria` = `cp`.`ID_Categoria`))) join `unidades_medida` `um` on((`p`.`Unidad_Medida` = `um`.`ID_Unidad`))) join `inventario_bodega` `ib` on((`p`.`ID_Producto` = `ib`.`ID_Producto`))) join `bodegas` `b` on((`ib`.`ID_Bodega` = `b`.`ID_Bodega`))) where (`p`.`Estado` = 'activo') order by `p`.`Descripcion`,`b`.`Nombre` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `vw_entradas_inventario`
--

/*!50001 DROP VIEW IF EXISTS `vw_entradas_inventario`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `vw_entradas_inventario` AS select `mi`.`ID_Movimiento` AS `ID_Movimiento`,`mi`.`Fecha` AS `Fecha`,`cm`.`ID_TipoMovimiento` AS `ID_TipoMovimiento`,`cm`.`Descripcion` AS `Tipo_Movimiento`,`cm`.`Letra` AS `Letra`,`mi`.`N_Factura_Externa` AS `N_Factura_Externa`,`mi`.`ID_Proveedor` AS `ID_Proveedor`,`p`.`Nombre` AS `Proveedor`,`mi`.`Tipo_Compra` AS `Tipo_Compra`,`mi`.`ID_Bodega` AS `ID_Bodega`,`b`.`Nombre` AS `Bodega`,`dmi`.`ID_Producto` AS `ID_Producto`,`pr`.`COD_Producto` AS `Codigo_Producto`,`pr`.`Descripcion` AS `Producto`,`dmi`.`Cantidad` AS `Cantidad`,`dmi`.`Costo_Unitario` AS `Costo_Unitario`,`dmi`.`Precio_Unitario` AS `Precio_Unitario`,`dmi`.`Subtotal` AS `Subtotal`,`mi`.`Estado` AS `Estado` from (((((`movimientos_inventario` `mi` join `catalogo_movimientos` `cm` on((`mi`.`ID_TipoMovimiento` = `cm`.`ID_TipoMovimiento`))) join `detalle_movimientos_inventario` `dmi` on((`mi`.`ID_Movimiento` = `dmi`.`ID_Movimiento`))) join `productos` `pr` on((`dmi`.`ID_Producto` = `pr`.`ID_Producto`))) join `bodegas` `b` on((`mi`.`ID_Bodega` = `b`.`ID_Bodega`))) left join `proveedores` `p` on((`mi`.`ID_Proveedor` = `p`.`ID_Proveedor`))) where ((`mi`.`ID_Empresa` = 1) and (`mi`.`Estado` = 'Activa') and (`cm`.`ID_TipoMovimiento` in (1,3))) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-11 12:09:34
