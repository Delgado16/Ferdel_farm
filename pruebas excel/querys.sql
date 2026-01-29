-- Tabla para vehículos asignados a vendedores
CREATE TABLE `vehiculos` (
  `ID_Vehiculo` int NOT NULL AUTO_INCREMENT,
  `Placa` varchar(20) NOT NULL,
  `Marca` varchar(100) DEFAULT NULL,
  `Modelo` varchar(100) DEFAULT NULL,
  `Anio` year DEFAULT NULL,
  `Estado` enum('Disponible','En Ruta','Mantenimiento','Inactivo') DEFAULT 'Disponible',
  `ID_Empresa` int NOT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Vehiculo`),
  UNIQUE KEY `uc_placa_empresa` (`Placa`, `ID_Empresa`),
  KEY `ID_Empresa` (`ID_Empresa`),
  CONSTRAINT `vehiculos_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

drop table rutas;
-- Tabla para rutas de vendedores
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

drop table asignacion_vendedores;

-- Tabla para asignación vendedor-ruta-vehículo
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
  PRIMARY KEY (`ID_Asignacion`),
  UNIQUE KEY `uc_vendedor_fecha` (`ID_Usuario`, `Fecha_Asignacion`),
  KEY `ID_Ruta` (`ID_Ruta`),
  KEY `ID_Vehiculo` (`ID_Vehiculo`),
  KEY `ID_Empresa` (`ID_Empresa`),
  KEY `ID_Usuario_Asigna` (`ID_Usuario_Asigna`),
  CONSTRAINT `asignacion_vendedores_ibfk_1` FOREIGN KEY (`ID_Usuario`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `asignacion_vendedores_ibfk_2` FOREIGN KEY (`ID_Ruta`) REFERENCES `rutas` (`ID_Ruta`),
  CONSTRAINT `asignacion_vendedores_ibfk_3` FOREIGN KEY (`ID_Vehiculo`) REFERENCES `vehiculos` (`ID_Vehiculo`),
  CONSTRAINT `asignacion_vendedores_ibfk_4` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `asignacion_vendedores_ibfk_5` FOREIGN KEY (`ID_Usuario_Asigna`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

drop table cargas_ruta;

-- Tabla para cargas iniciales de vendedores
CREATE TABLE `cargas_ruta` (
  `ID_Carga` int NOT NULL AUTO_INCREMENT,
  `ID_Asignacion` int NOT NULL,
  `ID_Bodega_Origen` int NOT NULL COMMENT 'Bodega de donde sale la carga',
  `Fecha_Carga` datetime NOT NULL,
  `Observaciones` text,
  `ID_Usuario_Carga` int DEFAULT NULL COMMENT 'Quién realiza la carga',
  `Estado` enum('Cargada','En Ruta','Descargada','Devuelta') DEFAULT 'Cargada',
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Carga`),
  KEY `ID_Asignacion` (`ID_Asignacion`),
  KEY `ID_Bodega_Origen` (`ID_Bodega_Origen`),
  KEY `ID_Usuario_Carga` (`ID_Usuario_Carga`),
  CONSTRAINT `cargas_ruta_ibfk_1` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `cargas_ruta_ibfk_2` FOREIGN KEY (`ID_Bodega_Origen`) REFERENCES `bodegas` (`ID_Bodega`),
  CONSTRAINT `cargas_ruta_ibfk_3` FOREIGN KEY (`ID_Usuario_Carga`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

drop table detalle_cargas_ruta;
-- Detalle de productos en la carga
CREATE TABLE `detalle_cargas_ruta` (
  `ID_Detalle_Carga` int NOT NULL AUTO_INCREMENT,
  `ID_Carga` int NOT NULL,
  `ID_Producto` int NOT NULL,
  `Cantidad` decimal(12,2) NOT NULL,
  `Costo_Unitario` decimal(12,2) DEFAULT NULL,
  `Precio_Unitario` decimal(12,2) DEFAULT NULL,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Detalle_Carga`),
  UNIQUE KEY `uc_carga_producto` (`ID_Carga`, `ID_Producto`),
  KEY `ID_Producto` (`ID_Producto`),
  CONSTRAINT `detalle_cargas_ruta_ibfk_1` FOREIGN KEY (`ID_Carga`) REFERENCES `cargas_ruta` (`ID_Carga`) ON DELETE CASCADE,
  CONSTRAINT `detalle_cargas_ruta_ibfk_2` FOREIGN KEY (`ID_Producto`) REFERENCES `productos` (`ID_Producto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Tabla para gastos de ruta
CREATE TABLE `gastos_ruta` (
  `ID_Gasto` int NOT NULL AUTO_INCREMENT,
  `ID_Asignacion` int NOT NULL,
  `Fecha_Gasto` date NOT NULL,
  `Tipo_Gasto` enum('Peaje','Parqueo','Combustible','Alimentación','Otros') NOT NULL,
  `Descripcion` varchar(500) NOT NULL,
  `Monto` decimal(10,2) NOT NULL,
  `Comprobante` varchar(100) DEFAULT NULL COMMENT 'Número de factura/comprobante',
  `ID_Usuario_Registra` int NOT NULL COMMENT 'Vendedor que registra el gasto',
  `Estado` enum('Pendiente','Aprobado','Rechazado','Pagado') DEFAULT 'Pendiente',
  `ID_Usuario_Aprueba` int DEFAULT NULL,
  `Fecha_Aprobacion` datetime DEFAULT NULL,
  `Comentario_Aprobacion` text,
  `Fecha_Creacion` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID_Gasto`),
  KEY `ID_Asignacion` (`ID_Asignacion`),
  KEY `ID_Usuario_Registra` (`ID_Usuario_Registra`),
  KEY `ID_Usuario_Aprueba` (`ID_Usuario_Aprueba`),
  KEY `idx_fecha_tipo` (`Fecha_Gasto`, `Tipo_Gasto`),
  KEY `idx_estado` (`Estado`),
  CONSTRAINT `gastos_ruta_ibfk_1` FOREIGN KEY (`ID_Asignacion`) REFERENCES `asignacion_vendedores` (`ID_Asignacion`),
  CONSTRAINT `gastos_ruta_ibfk_2` FOREIGN KEY (`ID_Usuario_Registra`) REFERENCES `usuarios` (`ID_Usuario`),
  CONSTRAINT `gastos_ruta_ibfk_3` FOREIGN KEY (`ID_Usuario_Aprueba`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;