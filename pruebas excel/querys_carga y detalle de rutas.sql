CREATE TABLE `movimientos_carga` (
  `ID_Movimiento` int NOT NULL AUTO_INCREMENT,
  `ID_Carga` int NOT NULL,
  `ID_Detalle_Carga` int NOT NULL,
  `ID_Cliente` int DEFAULT NULL,
  `ID_Pedido` int DEFAULT NULL,
  `Tipo_Movimiento` enum('Entrega_Pedido','Venta_Directa','Devolucion','Ajuste') NOT NULL,
  `Cantidad` decimal(12,2) NOT NULL,
  `Precio_Unitario` decimal(12,2) DEFAULT NULL,
  `Estado_Pago` enum('Pagado','Pendiente','Parcial') DEFAULT 'Pendiente',
  `Observaciones` text,
  `ID_Usuario_Registra` int DEFAULT NULL,
  `Fecha_Movimiento` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Movimiento`),
  KEY `ID_Carga` (`ID_Carga`),
  KEY `ID_Detalle_Carga` (`ID_Detalle_Carga`),
  KEY `ID_Cliente` (`ID_Cliente`),
  KEY `ID_Pedido` (`ID_Pedido`),
  KEY `Tipo_Movimiento` (`Tipo_Movimiento`),
  KEY `ID_Usuario_Registra` (`ID_Usuario_Registra`),
  CONSTRAINT `movimientos_carga_ibfk_1` FOREIGN KEY (`ID_Carga`) REFERENCES `carga_ruta` (`ID_Carga`),
  CONSTRAINT `movimientos_carga_ibfk_2` FOREIGN KEY (`ID_Detalle_Carga`) REFERENCES `detalle_carga` (`ID_Detalle_Carga`),
  CONSTRAINT `movimientos_carga_ibfk_3` FOREIGN KEY (`ID_Cliente`) REFERENCES `clientes` (`ID_Cliente`),
  CONSTRAINT `movimientos_carga_ibfk_4` FOREIGN KEY (`ID_Pedido`) REFERENCES `pedidos` (`ID_Pedido`),
  CONSTRAINT `movimientos_carga_ibfk_5` FOREIGN KEY (`ID_Usuario_Registra`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB;

CREATE TABLE `carga_ruta` (
  `ID_Carga` int NOT NULL AUTO_INCREMENT,
  `ID_Vendedor` int NOT NULL,
  `ID_Bodega_Origen` int NOT NULL,
  `Fecha_Salida` datetime NOT NULL,
  `Fecha_Retorno` datetime DEFAULT NULL,
  `Estado` enum('Preparando','En_Ruta','Completada','Cancelada') DEFAULT 'Preparando',
  `Observaciones` text,
  `ID_Usuario_Crea` int DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Carga`),
  KEY `ID_Vendedor` (`ID_Vendedor`),
  KEY `ID_Bodega_Origen` (`ID_Bodega_Origen`),
  KEY `ID_Usuario_Crea` (`ID_Usuario_Crea`),
  KEY `Estado` (`Estado`),
  CONSTRAINT `carga_ruta_ibfk_1` FOREIGN KEY (`ID_Vendedor`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `carga_ruta_ibfk_2` FOREIGN KEY (`ID_Bodega_Origen`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `carga_ruta_ibfk_3` FOREIGN KEY (`ID_Usuario_Crea`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB;

CREATE TABLE `detalle_carga` (
  `ID_Detalle_Carga` int NOT NULL AUTO_INCREMENT,
  `ID_Carga` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad_Salida` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Cantidad_Utilizada` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Cantidad_Devuelta` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Cantidad_Perdida` decimal(12,2) NOT NULL DEFAULT '0.00',
  `Fecha_Registro` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Detalle_Carga`),
  UNIQUE KEY `uc_carga_producto` (`ID_Carga`, `ID_Producto`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `detalle_carga_ibfk_1` FOREIGN KEY (`ID_Carga`) REFERENCES `carga_ruta` (`ID_Carga`) ON DELETE CASCADE,
  CONSTRAINT `detalle_carga_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB;

