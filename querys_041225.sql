--
-- Table structure for table `bitacora`
--

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
) ENGINE=InnoDB AUTO_INCREMENT=1572 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `bodegas`
--

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

--
-- Table structure for table `catalogo_movimientos`
--

DROP TABLE IF EXISTS `catalogo_movimientos`;
CREATE TABLE `catalogo_movimientos` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `categorias_producto`
--

DROP TABLE IF EXISTS `categorias_producto`;
CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `clientes`
--

DROP TABLE IF EXISTS `clientes`;
CREATE TABLE `clientes` (
  `ID_Cliente` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
  `Estado` enum('activo','inactivo') DEFAULT 'activo',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `clientes_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `cuentas_por_cobrar`
--

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
  `Saldo_Pendiente` decimal(12,2) DEFAULT '0.00',
  `ID_Factura` int DEFAULT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Factura` (`ID_Factura`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_1` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_3` FOREIGN KEY (`ID_Factura`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `cuentas_por_cobrar_ibfk_4` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `cuentas_por_pagar`
--

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
  PRIMARY KEY (`ID_Cuenta`),
  KEY `ID_Proveedor` (`ID_Proveedor`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `cuentas_por_pagar_ibfk_1` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `cuentas_por_pagar_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `cuentas_por_pagar_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `detalle_facturacion`
--

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
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `detalle_movimientos_inventario`
--

DROP TABLE IF EXISTS `detalle_movimientos_inventario`;
CREATE TABLE `detalle_movimientos_inventario` (
  `ID_Detalle_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_Movimiento` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad` decimal(15,4) NOT NULL,
  `Costo_Unitario` decimal(15,4) DEFAULT '0.00',
  `Precio_Unitario` decimal(15,4) DEFAULT '0.00',
  `Subtotal` decimal(15,4) DEFAULT '0.00',
  `Lote` varchar(100) DEFAULT NULL,
  `Fecha_Vencimiento` date DEFAULT NULL,
  `ID_Usuario_Creacion` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Detalle_Movimiento`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  KEY `idx_movimiento` (`ID_Movimiento`),
  KEY `idx_producto` (`ID_Producto`),
  KEY `idx_lote` (`Lote`),
  CONSTRAINT `detalle_movimientos_inventario_ibfk_1` FOREIGN KEY (`ID_Movimiento`) REFERENCES `movimientos_inventario` (`ID_Movimiento`) ON DELETE CASCADE,
  CONSTRAINT `detalle_movimientos_inventario_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`),
  CONSTRAINT `detalle_movimientos_inventario_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=54 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `empresa`
--

DROP TABLE IF EXISTS `empresa`;
CREATE TABLE `empresa` (
  `ID_Empresa` int NOT NULL AUTO_INCREMENT,
  `Nombre_Empresa` varchar(255) NOT NULL,
  `Direccion` varchar(240) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `Estado` enum('Activo','Inactivo') DEFAULT 'Activo',
  `RUC` varchar(20) DEFAULT NULL,
  PRIMARY KEY (`ID_Empresa`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `facturacion`
--

DROP TABLE IF EXISTS `facturacion`;
CREATE TABLE `facturacion` (
  `ID_Factura` int NOT NULL AUTO_INCREMENT,
  `Fecha` date NOT NULL,
  `IDCliente` int NOT NULL,
  `Credito_Contado` int DEFAULT NULL,
  `Observacion` text,
  `ID_Empresa` int NOT NULL,
  `ID_Usuario_Creacion` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Factura`),
  KEY `IDCliente` (`IDCliente`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Creacion` (`ID_Usuario_Creacion`),
  CONSTRAINT `facturacion_ibfk_1` FOREIGN KEY (`IDCliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `facturacion_ibfk_2` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `facturacion_ibfk_3` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `inventario_bodega`
--

DROP TABLE IF EXISTS `inventario_bodega`;
CREATE TABLE `inventario_bodega` (
  `ID_Bodega` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Existencias` decimal(12,2) DEFAULT '0.00',
  PRIMARY KEY (`ID_Bodega`,`ID_Producto`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `inventario_bodega_ibfk_1` FOREIGN KEY (`ID_Bodega`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `inventario_bodega_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `metodos_pago`
--

DROP TABLE IF EXISTS `metodos_pago`;
CREATE TABLE `metodos_pago` (
  `ID_MetodoPago` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_MetodoPago`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `movimientos_inventario`
--

DROP TABLE IF EXISTS `movimientos_inventario`;
CREATE TABLE `movimientos_inventario` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_TipoMovimiento` int NOT NULL,
  `N_Factura_Externa` varchar(255) DEFAULT NULL,
  `ID_Factura_Venta` int DEFAULT NULL,
  `Fecha` date NOT NULL,
  `ID_Proveedor` int DEFAULT NULL,
  `Tipo_Compra` enum('Contado','Credito') DEFAULT NULL,
  `Observacion` text,
  `ID_Empresa` int NOT NULL,
  `ID_Bodega` int NOT NULL,
  `ID_Bodega_Destino` int DEFAULT NULL,
  `UbicacionEntrega` text,
  `ID_Usuario_Creacion` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  `Fecha_Modificacion` datetime DEFAULT NULL,
  `ID_Usuario_Modificacion` int DEFAULT NULL,
  `Estado` enum('Pendiente','Completado','Cancelado') DEFAULT 'Pendiente',
  `ID_Cliente` int DEFAULT NULL,
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
  KEY `ID_Cliente` (`ID_Cliente`),
  CONSTRAINT `movimientos_inventario_ibfk_1` FOREIGN KEY (`ID_TipoMovimiento`) REFERENCES `catalogo_movimientos` (`ID_TipoMovimiento`),
  CONSTRAINT `movimientos_inventario_ibfk_2` FOREIGN KEY (`ID_Factura_Venta`) REFERENCES `facturacion` (`ID_Factura`),
  CONSTRAINT `movimientos_inventario_ibfk_3` FOREIGN KEY (`ID_Proveedor`) REFERENCES `proveedores` (`ID_Proveedor`),
  CONSTRAINT `movimientos_inventario_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `movimientos_inventario_ibfk_5` FOREIGN KEY (`ID_Bodega`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_6` FOREIGN KEY (`ID_Bodega_Destino`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `movimientos_inventario_ibfk_7` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `movimientos_inventario_ibfk_8` FOREIGN KEY (`ID_Usuario_Modificacion`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `movimientos_inventario_ibfk_9` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`)
) ENGINE=InnoDB AUTO_INCREMENT=43 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `pagos_cuentascobrar`
--

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
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `pagos_cuentaspagar`
--

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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `productos`
--

DROP TABLE IF EXISTS `productos`;
CREATE TABLE `productos` (
  `ID_Producto` int NOT NULL AUTO_INCREMENT,
  `COD_Producto` varchar(100) DEFAULT NULL,
  `Descripcion` varchar(255) NOT NULL,
  `Unidad_Medida` int DEFAULT NULL,
  `Estado` int DEFAULT '1',
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
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `proveedores`
--

DROP TABLE IF EXISTS `proveedores`;
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `unidades_medida`
--

DROP TABLE IF EXISTS `unidades_medida`;
CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Table structure for table `usuarios`
--

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