
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
) ENGINE=InnoDB AUTO_INCREMENT=5931 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


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
) ENGINE=InnoDB AUTO_INCREMENT=141 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `caja_movimientos`
--

LOCK TABLES `caja_movimientos` WRITE;
/*!40000 ALTER TABLE `caja_movimientos` DISABLE KEYS */;
INSERT INTO `caja_movimientos` VALUES (1,'2025-12-27 14:26:26','ENTRADA','Venta al contado - Factura #88 - Cliente: Jonathan',16000.00,88,NULL,6,'FAC-00088',0,NULL,NULL,'ACTIVO',NULL,NULL),(2,'2025-12-27 14:36:24','ENTRADA','Pago CxC - Josue Delgado - Documento: FAC-00078 - N/A',1900.00,NULL,6,6,'PAGO-CXC-00006',0,NULL,NULL,'ACTIVO',NULL,NULL),(3,'2025-12-27 14:49:55','ENTRADA','Pago CxC - Leonardo - Documento: FAC-00052 - N/A',11000.50,NULL,7,6,'PAGO-CXC-00007',0,NULL,NULL,'ACTIVO',NULL,NULL),(4,'2025-12-27 14:56:56','ENTRADA','Pago CxC - Leonardo - Documento: FAC-00059 - n/a',800.00,NULL,8,6,'PAGO-CXC-00008',0,NULL,NULL,'ACTIVO',NULL,NULL),(5,'2025-12-27 14:57:58','ENTRADA','Pago CxC - Leonardo - Documento: FAC-00059 - N//A',800.00,NULL,9,6,'PAGO-CXC-00009',0,NULL,NULL,'ACTIVO',NULL,NULL),(6,'2025-12-27 15:19:04','ENTRADA','Pago CxC - Fared - Documento: FAC-000008 - N/A',140.00,NULL,10,6,'PAGO-CXC-00010',0,NULL,NULL,'ACTIVO',NULL,NULL),(7,'2025-12-27 15:22:20','ENTRADA','Venta al contado - Factura #89 - Cliente: Fared',14000.00,89,NULL,6,'FAC-00089',0,NULL,NULL,'ACTIVO',NULL,NULL),(8,'2025-12-27 15:37:49','ENTRADA','Pago CxC - Fared - Documento: FAC-00057 - n/a',1000.00,NULL,11,6,'PAGO-CXC-00011',0,NULL,NULL,'ACTIVO',NULL,NULL),(9,'2025-12-27 15:40:41','ENTRADA','Pago CxC - Fared - Documento: FAC-00057 - n/a',60.00,NULL,12,6,'PAGO-CXC-00012',0,NULL,NULL,'ACTIVO',NULL,NULL),(10,'2025-12-27 15:41:33','ENTRADA','Pago CxC - Fared - Documento: FAC-00057 - adasdasd',300.00,NULL,13,6,'PAGO-CXC-00013',0,NULL,NULL,'ACTIVO',NULL,NULL),(11,'2025-12-29 13:46:59','ENTRADA','Pago CxC - Fared - Documento: FAC-00056 - nada',7000.00,NULL,14,6,'PAGO-CXC-00014',0,NULL,NULL,'ACTIVO',NULL,NULL),(12,'2025-12-30 11:05:05','ENTRADA','Venta al contado - Factura #90 - Cliente: Jahir',19500.00,90,NULL,6,'FAC-00090',0,NULL,NULL,'ACTIVO',NULL,NULL),(13,'2025-12-30 11:09:06','ENTRADA','Pago CxC - Fared - Documento: FAC-00016 - n/a',3240.00,NULL,15,6,'PAGO-CXC-00015',0,NULL,NULL,'ACTIVO',NULL,NULL),(14,'2025-12-30 11:25:23','ENTRADA','Venta al contado - Factura #91 - Cliente: Fared',7450.00,91,NULL,6,'FAC-00091',0,NULL,NULL,'ACTIVO',NULL,NULL),(15,'2025-12-30 11:53:31','ENTRADA','Venta al contado - Factura #92 - Cliente: Fared',1950.00,92,NULL,1,'FAC-00092',0,NULL,NULL,'ACTIVO',NULL,NULL),(16,'2025-12-30 11:54:43','ENTRADA','Venta al contado - Factura #93 - Cliente: Jonathan',30400.00,93,NULL,1,'FAC-00093',0,NULL,NULL,'ACTIVO',NULL,NULL),(17,'2025-12-30 14:03:43','ENTRADA','Apertura de caja',0.01,NULL,NULL,NULL,'APERTURA',0,NULL,NULL,'ACTIVO',NULL,NULL),(18,'2025-12-30 14:10:34','SALIDA','Pago Pelon',1500.00,NULL,NULL,NULL,'Sueldo',0,NULL,NULL,'ACTIVO',NULL,NULL),(19,'2025-12-30 15:14:06','ENTRADA','Venta al contado - Factura #94 - Cliente: Clientes Varios',16500.00,94,NULL,6,'FAC-00094',0,NULL,NULL,'ACTIVO',NULL,NULL),(20,'2025-12-30 15:30:18','SALIDA','compra de bujia',500.00,NULL,NULL,NULL,'Repuestos',0,NULL,NULL,'ACTIVO',NULL,NULL),(21,'2025-12-30 19:12:13','SALIDA','Cierre de caja -  - Diferencia: $+7000.00',77040.01,NULL,NULL,NULL,'CIERRE',0,NULL,NULL,'ACTIVO',NULL,NULL),(22,'2026-01-02 18:06:10','ENTRADA','Apertura de caja - Saldo Inicial',10000.00,NULL,NULL,NULL,'APERTURA',0,NULL,NULL,'ACTIVO',NULL,NULL),(23,'2026-01-02 18:07:09','ENTRADA','Venta al contado - Factura #95 - Cliente: Fared',19500.00,95,NULL,1,'FAC-00095',0,NULL,NULL,'ACTIVO',NULL,NULL),(24,'2026-01-02 18:13:01','SALIDA','CANCELACIÓN TOTAL: Venta al contado - Factura #95 - Cliente: Fared',19500.00,95,NULL,NULL,'CANC_TOTAL_FAC-00095',1,23,'CANCELACIÓN COMPLETA - si comprendo','ACTIVO',NULL,NULL),(25,'2026-01-05 12:57:37','ENTRADA','Apertura de caja',100.00,NULL,NULL,1,'APERTURA',0,NULL,NULL,'ACTIVO',NULL,NULL),(26,'2026-01-05 15:41:00','ENTRADA','Venta al contado - Factura #96 - Cliente: Clientes Varios',11700.00,96,NULL,1,'FAC-00096',0,NULL,NULL,'ACTIVO',NULL,NULL),(27,'2026-01-05 15:41:43','ENTRADA','Pago CxC - Fared - Documento: FAC-00057 - dasdasd',400.00,NULL,16,1,'PAGO-CXC-00016',0,NULL,NULL,'ACTIVO',NULL,NULL),(28,'2026-01-05 15:45:59','SALIDA','Pago a Pelon',150.00,NULL,NULL,1,'PAGO SUELDO',0,NULL,'mal ingreso','ANULADO','2026-01-05 15:52:05',1),(29,'2026-01-05 15:52:05','ENTRADA','AJUSTE: Pago a Pelon',150.00,NULL,NULL,1,'AJUSTE',1,28,'Anulación del movimiento #28. Motivo: mal ingreso','ACTIVO',NULL,NULL),(30,'2026-01-05 15:52:55','SALIDA','Pago a Pelon',200.00,NULL,NULL,1,'PAGO SUELDO',0,NULL,NULL,'ACTIVO',NULL,NULL),(31,'2026-01-05 16:39:29','ENTRADA','Venta al contado - Factura #97 - Cliente: Clientes Varios',1950.00,97,NULL,1,'FAC-00097',0,NULL,NULL,'ACTIVO',NULL,NULL),(32,'2026-01-05 16:39:54','SALIDA','REVERSIÓN VENTA #97 - Anulación - Cliente: Clientes Varios - Método original: efectivo',1950.00,97,NULL,1,'REV-31',0,NULL,NULL,'ACTIVO',NULL,NULL),(33,'2026-01-05 22:58:42','SALIDA','Cierre de caja - Saldo: $12150.00 - simon',12150.00,NULL,NULL,1,'CIERRE',0,NULL,NULL,'ACTIVO',NULL,NULL),(34,'2026-01-06 08:33:45','ENTRADA','Apertura de caja - $14000.00',14000.00,NULL,NULL,6,'APERTURA',0,NULL,NULL,'ACTIVO',NULL,NULL),(35,'2026-01-06 08:35:53','ENTRADA','Venta al contado - Factura #98 - Cliente: Clientes Varios',1950.00,98,NULL,6,'FAC-00098',0,NULL,NULL,'ACTIVO',NULL,NULL),(36,'2026-01-06 08:37:02','ENTRADA','Venta al contado - Factura #99 - Cliente: Fared',2200.00,99,NULL,6,'FAC-00099',0,NULL,NULL,'ACTIVO',NULL,NULL),(37,'2026-01-06 08:38:36','ENTRADA','Venta al contado - Factura #100 - Cliente: Fared',2000.00,100,NULL,6,'FAC-00100',0,NULL,NULL,'ACTIVO',NULL,NULL),(38,'2026-01-06 08:39:05','SALIDA','REVERSIÓN VENTA #100 - Anulación - Cliente: Fared - Método original: efectivo',2000.00,100,NULL,6,'REV-37',0,NULL,NULL,'ACTIVO',NULL,NULL),(39,'2026-01-06 08:44:04','ENTRADA','Venta al contado - Factura #101 - Cliente: Clientes Varios',1950.00,101,NULL,6,'FAC-00101',0,NULL,NULL,'ACTIVO',NULL,NULL),(40,'2026-01-06 08:44:21','SALIDA','REVERSIÓN VENTA #101 - Anulación - Cliente: Clientes Varios - Método original: efectivo',1950.00,101,NULL,6,'REV-39',0,NULL,NULL,'ACTIVO',NULL,NULL),(41,'2026-01-06 08:45:38','ENTRADA','Venta al contado - Factura #102 - Cliente: Clientes Varios',260.00,102,NULL,6,'FAC-00102',0,NULL,NULL,'ACTIVO',NULL,NULL),(42,'2026-01-06 08:46:03','SALIDA','REVERSIÓN VENTA #102 - Anulación - Cliente: Clientes Varios - Método original: efectivo',260.00,102,NULL,6,'REV-41',0,NULL,NULL,'ACTIVO',NULL,NULL),(43,'2026-01-06 08:48:43','ENTRADA','Venta al contado - Factura #103 - Cliente: Clientes Varios',195.00,103,NULL,6,'FAC-00103',0,NULL,NULL,'ACTIVO',NULL,NULL),(44,'2026-01-06 08:52:52','ENTRADA','Pago CxC - Fared - Documento: FAC-00016 - N/A',3000.00,NULL,17,6,'PAGO-CXC-00017',0,NULL,NULL,'ACTIVO',NULL,NULL),(45,'2026-01-06 08:54:36','ENTRADA','Pago CxC - Fared - Documento: FAC-00019 - N/A',300.00,NULL,18,6,'PAGO-CXC-00018',0,NULL,NULL,'ACTIVO',NULL,NULL),(46,'2026-01-06 08:56:12','ENTRADA','Pago CxC - Fared - Documento: FAC-00019 - Pago registrado',340.00,NULL,19,6,'PAGO-CXC-00019',0,NULL,NULL,'ACTIVO',NULL,NULL),(47,'2026-01-06 09:00:12','SALIDA','Pago Luz',400.00,NULL,NULL,6,'Servicio Energético',0,NULL,NULL,'ANULADO','2026-01-06 09:00:57',6),(48,'2026-01-06 09:00:57','ENTRADA','Anulación: Pago Luz',400.00,NULL,NULL,6,'ANULACION',0,47,NULL,'ANULADO','2026-01-06 09:12:13',6),(49,'2026-01-06 09:11:31','ENTRADA','Venta al contado - Factura #104 - Cliente: Jahir',200.00,104,NULL,6,'FAC-00104',0,NULL,'Anulado por reversión de venta #104. mal ingreso de cantidad de producto','ANULADO','2026-01-06 09:13:22',6),(50,'2026-01-06 09:12:13','SALIDA','Anulación: Anulación: Pago Luz',400.00,NULL,NULL,6,'ANULACION',0,48,NULL,'ACTIVO',NULL,NULL),(51,'2026-01-06 09:13:22','SALIDA','REVERSIÓN VENTA #104 - Anulación - Cliente: Jahir - Método original: efectivo',200.00,104,NULL,6,'REV-49',1,49,NULL,'ACTIVO',NULL,NULL),(52,'2026-01-06 09:14:43','SALIDA','Compra bujia',190.00,NULL,NULL,6,'gasto',0,NULL,NULL,'ANULADO','2026-01-06 09:14:58',6),(53,'2026-01-06 09:14:58','ENTRADA','Anulación: Compra bujia',190.00,NULL,NULL,6,'ANULACION',0,52,NULL,'ANULADO','2026-01-06 09:19:33',6),(54,'2026-01-06 09:16:14','SALIDA','litro de cener',100.00,NULL,NULL,6,'gastos operativos',0,NULL,NULL,'ANULADO','2026-01-06 09:16:39',6),(55,'2026-01-06 09:16:39','ENTRADA','Anulación: litro de cener',100.00,NULL,NULL,6,'ANULACION',0,54,NULL,'ANULADO','2026-01-06 09:19:06',6),(56,'2026-01-06 09:17:49','SALIDA','pago a chepito',200.00,NULL,NULL,6,'Pago Sueldo',0,NULL,NULL,'ANULADO','2026-01-06 09:18:11',6),(57,'2026-01-06 09:18:11','ENTRADA','Anulación: pago a chepito',200.00,NULL,NULL,6,'ANULACION',0,56,NULL,'ANULADO','2026-01-06 09:18:45',6),(58,'2026-01-06 09:18:45','SALIDA','Anulación: Anulación: pago a chepito',200.00,NULL,NULL,6,'ANULACION',0,57,NULL,'ACTIVO',NULL,NULL),(59,'2026-01-06 09:19:06','SALIDA','Anulación: Anulación: litro de cener',100.00,NULL,NULL,6,'ANULACION',0,55,NULL,'ACTIVO',NULL,NULL),(60,'2026-01-06 09:19:33','SALIDA','Anulación: Anulación: Compra bujia',190.00,NULL,NULL,6,'ANULACION',0,53,NULL,'ACTIVO',NULL,NULL),(61,'2026-01-06 10:52:58','ENTRADA','Venta al contado - Factura #105 - Cliente: Clientes Varios',2000.00,105,NULL,6,'FAC-00105',0,NULL,NULL,'ACTIVO',NULL,NULL),(62,'2026-01-06 13:42:30','ENTRADA','Venta al contado - Factura #106 - Cliente: Fared',2000.00,106,NULL,6,'FAC-00106',0,NULL,NULL,'ACTIVO',NULL,NULL),(63,'2026-01-06 14:34:00','ENTRADA','Pelon ruta',59200.00,NULL,NULL,6,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(64,'2026-01-06 14:38:06','SALIDA','Pago a Pelon',1800.00,NULL,NULL,6,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(65,'2026-01-06 14:41:34','ENTRADA','Venta al contado - Factura #107 - Cliente: Clientes Varios',200.00,107,NULL,6,'FAC-00107',0,NULL,NULL,'ACTIVO',NULL,NULL),(66,'2026-01-07 08:08:51','ENTRADA','Apertura de caja',100.00,NULL,NULL,6,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(67,'2026-01-07 08:13:21','ENTRADA','Venta al contado - Factura #108 - Cliente: Clientes Varios',3800.00,108,NULL,6,'FAC-00108',0,NULL,NULL,'ACTIVO',NULL,NULL),(68,'2026-01-07 08:18:08','ENTRADA','Pago CxC - Jorges - Documento: FAC-00020 - N/A',810.00,NULL,20,6,'PAGO-CXC-00020',0,NULL,NULL,'ACTIVO',NULL,NULL),(69,'2026-01-07 09:00:37','ENTRADA','Ruta Masaya',20000.00,NULL,NULL,6,'',0,NULL,NULL,'ACTIVO',NULL,NULL),(70,'2026-01-07 09:14:16','SALIDA','100 separadores',300.00,NULL,NULL,6,'',0,NULL,NULL,'ACTIVO',NULL,NULL),(71,'2026-01-07 09:21:37','ENTRADA','Venta de huevos fuera de caja',200.00,NULL,NULL,6,'Venta huevo',0,NULL,NULL,'ACTIVO',NULL,NULL),(72,'2026-01-07 13:39:07','ENTRADA','Venta al contado - Factura #109 - Cliente: Clientes Varios',170000.00,109,NULL,6,'FAC-00109',0,NULL,NULL,'ACTIVO',NULL,NULL),(73,'2026-01-07 13:40:53','ENTRADA','Venta al contado - Factura #110 - Cliente: Fared',38000.00,110,NULL,6,'FAC-00110',0,NULL,NULL,'ACTIVO',NULL,NULL),(74,'2026-01-07 14:03:29','ENTRADA','Venta al contado - Factura #111 - Cliente: Jahir',2000.00,111,NULL,1,'FAC-00111',0,NULL,NULL,'ACTIVO',NULL,NULL),(75,'2026-01-07 14:08:44','ENTRADA','Venta al contado - Factura #112 - Cliente: Jonathan',2000.00,112,NULL,1,'FAC-00112',0,NULL,NULL,'ACTIVO',NULL,NULL),(76,'2026-01-07 14:12:27','ENTRADA','Venta al contado - Factura #113 - Cliente: Jonathan',24000.00,113,NULL,1,'FAC-00113',0,NULL,NULL,'ACTIVO',NULL,NULL),(77,'2026-01-07 14:13:28','ENTRADA','Venta al contado - Factura #114 - Cliente: Fared',200.00,114,NULL,1,'FAC-00114',0,NULL,NULL,'ACTIVO',NULL,NULL),(78,'2026-01-07 14:21:35','ENTRADA','Venta al contado - Factura #115 - Cliente: Josue Delgado',6250.00,115,NULL,1,'FAC-00115',0,NULL,NULL,'ACTIVO',NULL,NULL),(79,'2026-01-07 15:07:01','ENTRADA','Venta al contado - Factura #116 - Cliente: Jonathan',2350.00,116,NULL,1,'FAC-00116',0,NULL,NULL,'ACTIVO',NULL,NULL),(80,'2026-01-07 15:16:57','ENTRADA','Venta al contado - Factura #117 - Cliente: Josue Delgado',1885.00,117,NULL,1,'FAC-00117',0,NULL,NULL,'ACTIVO',NULL,NULL),(81,'2026-01-07 15:37:00','ENTRADA','Venta al contado - Factura #118 - Cliente: Josue Delgado',9900.00,118,NULL,1,'FAC-00118',0,NULL,NULL,'ACTIVO',NULL,NULL),(82,'2026-01-07 15:46:12','ENTRADA','Venta al contado - Factura #119 - Cliente: Fared',11950.00,119,NULL,1,'FAC-00119',0,NULL,NULL,'ACTIVO',NULL,NULL),(83,'2026-01-07 15:50:27','ENTRADA','Venta al contado - Factura #120 - Cliente: Jorges',22000.00,120,NULL,1,'FAC-00120',0,NULL,'Anulado por reversión de venta #120. mal ingreso de datos','ANULADO','2026-01-07 15:51:16',1),(84,'2026-01-07 15:51:16','SALIDA','REVERSIÓN VENTA #120 - Anulación - Cliente: Jorges - Método original: efectivo',22000.00,120,NULL,1,'REV-83',1,83,NULL,'ACTIVO',NULL,NULL),(85,'2026-01-07 16:14:59','ENTRADA','Venta al contado - Factura #121 - Cliente: Clientes Varios',2000.00,121,NULL,1,'FAC-00121',0,NULL,'ANULADO POR ANULACIÓN DE VENTA #121: venta incorrecta','ANULADO','2026-01-07 16:15:30',1),(86,'2026-01-07 16:15:30','SALIDA','ANULACIÓN VENTA #121 - Cliente: Clientes Varios - Método original: efectivo',2000.00,121,NULL,1,'ANUL-VTA-121-20260107161530',1,121,'Anulación de venta #121. Motivo: venta incorrecta. ','ACTIVO',NULL,NULL),(87,'2026-01-08 08:48:31','ENTRADA','Apertura de caja',1.00,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(88,'2026-01-08 09:04:30','ENTRADA','Venta al contado - Factura #122 - Cliente: Clientes Varios',200.00,122,NULL,1,'FAC-00122',0,NULL,'ANULADO POR ANULACIÓN DE VENTA #122: error','ANULADO','2026-01-08 09:05:07',1),(89,'2026-01-08 09:05:07','SALIDA','ANULACIÓN VENTA #122 - Cliente: Clientes Varios - Método original: efectivo',200.00,122,NULL,1,'ANUL-VTA-122-20260108090507',1,122,'Anulación de venta #122. Motivo: error. ','ANULADO',NULL,NULL),(90,'2026-01-08 09:19:35','ENTRADA','Venta al contado - Factura #123 - Cliente: Clientes Varios',190.00,123,NULL,1,'FAC-00123',0,NULL,'ANULADO POR ANULACIÓN DE VENTA #123: sdfsdfsdfsdf','ANULADO','2026-01-08 09:21:00',1),(91,'2026-01-09 13:26:51','ENTRADA','Venta al contado - Factura #124 - Cliente: Clientes Varios',2000.00,124,NULL,1,'FAC-00124',0,NULL,NULL,'ACTIVO',NULL,NULL),(92,'2026-01-09 13:27:18','ENTRADA','Apertura de caja',10.00,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(93,'2026-01-09 13:28:40','SALIDA','compra de sener',150.00,NULL,NULL,1,'gasto',0,NULL,NULL,'ACTIVO',NULL,NULL),(94,'2026-01-09 15:16:42','ENTRADA','Venta al contado - Factura #125 - Cliente: Clientes Varios',2000.00,125,NULL,1,'FAC-00125',0,NULL,NULL,'ACTIVO',NULL,NULL),(95,'2026-01-09 15:26:29','ENTRADA','Venta al contado - Factura #127 - Cliente: Jonathan',26600.00,127,NULL,1,'FAC-00127',0,NULL,NULL,'ACTIVO',NULL,NULL),(96,'2026-01-09 15:47:28','ENTRADA','Venta al contado - Factura #128 - Cliente: Fared',2000.00,128,NULL,1,'FAC-00128',0,NULL,NULL,'ACTIVO',NULL,NULL),(97,'2026-01-10 10:08:47','ENTRADA','Apertura de caja',0.10,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(98,'2026-01-10 10:16:25','ENTRADA','Venta al contado - Factura #129 - Cliente: Clientes Varios',4600.00,129,NULL,1,'FAC-00129',0,NULL,NULL,'ACTIVO',NULL,NULL),(99,'2026-01-13 09:50:42','ENTRADA','Apertura de caja',1200.00,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(100,'2026-01-13 09:51:13','ENTRADA','Venta al contado - Factura #130 - Cliente: Clientes Varios',640.00,130,NULL,1,'FAC-00130',0,NULL,NULL,'ACTIVO',NULL,NULL),(101,'2026-01-13 09:51:48','ENTRADA','Venta al contado - Factura #131 - Cliente: Clientes Varios',165.00,131,NULL,1,'FAC-00131',0,NULL,NULL,'ACTIVO',NULL,NULL),(102,'2026-01-13 11:28:28','ENTRADA','Venta al contado - Factura #132 - Cliente: Clientes Varios',390.00,132,NULL,1,'FAC-00132',0,NULL,NULL,'ACTIVO',NULL,NULL),(103,'2026-01-13 11:56:40','ENTRADA','Venta al contado - Factura #133 - Cliente: Clientes Varios',5400.00,133,NULL,1,'FAC-00133',0,NULL,NULL,'ACTIVO',NULL,NULL),(104,'2026-01-13 13:47:33','ENTRADA','pago factura anterior',9750.00,NULL,NULL,1,'Cuate factura anterior',0,NULL,NULL,'ACTIVO',NULL,NULL),(105,'2026-01-13 14:36:42','ENTRADA','Venta al contado - Factura #134 - Cliente: Clientes Varios',190.00,134,NULL,1,'FAC-00134',0,NULL,NULL,'ACTIVO',NULL,NULL),(106,'2026-01-13 14:55:53','ENTRADA','huevo blanco',3500.00,NULL,NULL,1,'Efectivo',0,NULL,NULL,'ACTIVO',NULL,NULL),(107,'2026-01-13 15:28:20','ENTRADA','Venta al contado - Factura #135 - Cliente: Clientes Varios',200.00,135,NULL,1,'FAC-00135',0,NULL,NULL,'ACTIVO',NULL,NULL),(108,'2026-01-13 15:33:07','ENTRADA','RUTA DE YERI',44430.00,NULL,NULL,1,'RUTA',0,NULL,NULL,'ACTIVO',NULL,NULL),(109,'2026-01-13 16:04:55','ENTRADA','Venta al contado - Factura #136 - Cliente: Clientes Varios',1900.00,136,NULL,1,'FAC-00136',0,NULL,NULL,'ACTIVO',NULL,NULL),(110,'2026-01-13 16:05:44','ENTRADA','Don juan 3 cajillas',480.00,NULL,NULL,1,'Efectivo',0,NULL,NULL,'ACTIVO',NULL,NULL),(111,'2026-01-14 08:32:40','ENTRADA','Apertura de caja',0.01,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(112,'2026-01-14 14:22:28','ENTRADA','Venta al contado - Factura #137 - Cliente: Fared',200.00,137,NULL,1,'FAC-00137',0,NULL,NULL,'ACTIVO',NULL,NULL),(113,'2026-01-14 14:55:31','SALIDA','j',0.01,NULL,NULL,1,'Salida',0,NULL,NULL,'ACTIVO',NULL,NULL),(114,'2026-01-14 15:00:46','ENTRADA','Venta al contado - Factura #138 - Cliente: Clientes Varios',140.00,138,NULL,1,'FAC-00138',0,NULL,NULL,'ACTIVO',NULL,NULL),(115,'2026-01-14 15:20:06','ENTRADA','Venta al contado - Factura #139 - Cliente: Clientes Varios',2400.00,139,NULL,1,'FAC-00139',0,NULL,NULL,'ACTIVO',NULL,NULL),(116,'2026-01-15 10:18:57','ENTRADA','Apertura de caja',0.01,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(117,'2026-01-16 15:17:49','ENTRADA','Venta al contado - Factura #142 - Cliente: Clientes Varios',2770.00,142,NULL,1,'FAC-00142',0,NULL,NULL,'ACTIVO',NULL,NULL),(118,'2026-01-16 15:27:25','ENTRADA','Venta al contado - Factura #143 - Cliente: Jahir',1900.00,143,NULL,1,'FAC-00143',0,NULL,NULL,'ACTIVO',NULL,NULL),(119,'2026-01-16 15:41:10','ENTRADA','Venta al contado - Factura #144 - Cliente: Agroservicios',6420.00,144,NULL,1,'FAC-00144',0,NULL,NULL,'ACTIVO',NULL,NULL),(120,'2026-01-17 08:23:30','ENTRADA','Venta al contado - Factura #145 - Cliente: Kenny',6420.00,145,NULL,1,'FAC-00145',0,NULL,NULL,'ACTIVO',NULL,NULL),(121,'2026-01-17 08:40:28','ENTRADA','Venta al contado - Factura #146 - Cliente: Agroservicios',2150.50,146,NULL,1,'FAC-00146',0,NULL,NULL,'ACTIVO',NULL,NULL),(122,'2026-01-17 11:19:05','ENTRADA','Venta al contado - Factura #147 - Cliente: Fared',40000.00,147,NULL,8,'FAC-00147',0,NULL,NULL,'ACTIVO',NULL,NULL),(123,'2026-01-17 11:23:38','ENTRADA','Venta al contado - Factura #148 - Cliente: Kenny',3390.00,148,NULL,8,'FAC-00148',0,NULL,NULL,'ACTIVO',NULL,NULL),(124,'2026-01-19 09:30:58','ENTRADA','Venta al contado - Factura #150 - Cliente: Jeshua',2000.00,150,NULL,8,'FAC-00150',0,NULL,NULL,'ACTIVO',NULL,NULL),(125,'2026-01-19 11:13:14','ENTRADA','Venta al contado - Factura #152 - Cliente: Josue Delgado',4000.00,152,NULL,2,'FAC-00152',0,NULL,NULL,'ACTIVO',NULL,NULL),(126,'2026-01-19 11:14:30','ENTRADA','Venta al contado - Factura #153 - Cliente: Agroservicios',107000.00,153,NULL,2,'FAC-00153',0,NULL,NULL,'ACTIVO',NULL,NULL),(127,'2026-01-19 12:04:55','ENTRADA','Venta al contado - Factura #154 - Cliente: Agroservicios',1070.00,154,NULL,2,'FAC-00154',0,NULL,NULL,'ACTIVO',NULL,NULL),(128,'2026-01-19 15:52:45','ENTRADA','Venta al contado - Factura #155 - Cliente: Agroservicios',1070.00,155,NULL,2,'FAC-00155',0,NULL,NULL,'ACTIVO',NULL,NULL),(129,'2026-01-19 15:53:27','ENTRADA','Venta al contado - Factura #156 - Cliente: Agroservicios',1070.00,156,NULL,2,'FAC-00156',0,NULL,NULL,'ACTIVO',NULL,NULL),(130,'2026-01-19 15:54:39','ENTRADA','Venta al contado - Factura #157 - Cliente: Agroservicios',2500.00,157,NULL,2,'FAC-00157',0,NULL,NULL,'ACTIVO',NULL,NULL),(131,'2026-01-19 15:56:58','ENTRADA','Venta al contado - Factura #158 - Cliente: Jonathan',2000.00,158,NULL,2,'FAC-00158',0,NULL,NULL,'ACTIVO',NULL,NULL),(132,'2026-01-19 15:58:05','ENTRADA','Venta al contado - Factura #159 - Cliente: Josue Delgado',4000.00,159,NULL,2,'FAC-00159',0,NULL,NULL,'ACTIVO',NULL,NULL),(133,'2026-01-20 08:21:12','ENTRADA','Venta al contado - Factura #160 - Cliente: Agroservicios',3210.00,160,NULL,2,'FAC-00160',0,NULL,NULL,'ACTIVO',NULL,NULL),(134,'2026-01-21 09:01:19','ENTRADA','Venta al contado - Factura #161 - Cliente: Agroservicios',10700.00,161,NULL,2,'FAC-00161',0,NULL,NULL,'ACTIVO',NULL,NULL),(135,'2026-01-22 16:03:12','ENTRADA','Venta desde pedido #8 - Factura #162 - Cliente: Josue Delgado',400.00,162,NULL,8,'FAC-00162',0,NULL,NULL,'ACTIVO',NULL,NULL),(136,'2026-01-23 11:02:52','ENTRADA','Venta desde pedido #9 - Factura #163 - Cliente: Kenny',2320.00,163,NULL,8,'FAC-00163',0,NULL,NULL,'ACTIVO',NULL,NULL),(137,'2026-01-23 11:26:21','ENTRADA','Venta desde pedido #9 - Factura #164 - Cliente: Kenny',2320.00,164,NULL,8,'FAC-00164',0,NULL,NULL,'ACTIVO',NULL,NULL),(138,'2026-01-23 14:25:13','ENTRADA','Venta desde pedido #10 - Factura #165 - Cliente: Jeshua',2750.00,165,NULL,2,'FAC-00165',0,NULL,NULL,'ACTIVO',NULL,NULL),(139,'2026-01-24 09:27:11','ENTRADA','Apertura de caja',10.00,NULL,NULL,1,NULL,0,NULL,NULL,'ACTIVO',NULL,NULL),(140,'2026-01-24 09:27:47','ENTRADA','Venta al contado - Factura #166 - Cliente: Clientes Varios',700.00,166,NULL,1,'FAC-00166',0,NULL,NULL,'ACTIVO',NULL,NULL);
/*!40000 ALTER TABLE `caja_movimientos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `catalogo_movimientos`
--

DROP TABLE IF EXISTS `catalogo_movimientos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `catalogo_movimientos` (
  `ID_TipoMovimiento` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) DEFAULT NULL,
  `Adicion` varchar(255) DEFAULT NULL,
  `Letra` varchar(10) DEFAULT NULL,
  PRIMARY KEY (`ID_TipoMovimiento`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `catalogo_movimientos`
--

LOCK TABLES `catalogo_movimientos` WRITE;
/*!40000 ALTER TABLE `catalogo_movimientos` DISABLE KEYS */;
INSERT INTO `catalogo_movimientos` VALUES (1,'Compra','Entrada por compra','E'),(2,'Venta','Salida por venta','S'),(3,'Producción','Entrada por producción','E'),(4,'Consumo','Salida por consumo','S'),(5,'Ajuste Salida','Ajuste de salida de inventario','S'),(6,'Traslado','Movimiento Interno','T'),(7,'Merma','Perdidas','S'),(8,'Ajuste Entrada','Ajuste de entrada de inventario','E'),(9,'Anulacion Compra','Anular compra proveedores','S'),(10,'Anulacion Venta','Anular venta clientes','E');
/*!40000 ALTER TABLE `catalogo_movimientos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `categorias_producto`
--

DROP TABLE IF EXISTS `categorias_producto`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `categorias_producto` (
  `ID_Categoria` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_Categoria`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `categorias_producto`
--

LOCK TABLES `categorias_producto` WRITE;
/*!40000 ALTER TABLE `categorias_producto` DISABLE KEYS */;
INSERT INTO `categorias_producto` VALUES (1,'Huevos'),(2,'Pollos'),(3,'Gallinas'),(4,'Alimentos'),(5,'Medicamentos'),(6,'Vacunas'),(7,'Separadores'),(8,'Limpieza y Desinfectantes'),(9,'Equipos'),(10,'Servicios'),(11,'Granza'),(12,'Gallinaza');
/*!40000 ALTER TABLE `categorias_producto` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `clientes`
--

DROP TABLE IF EXISTS `clientes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clientes` (
  `ID_Cliente` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  `Telefono` varchar(50) DEFAULT NULL,
  `Direccion` text,
  `RUC_CEDULA` varchar(50) DEFAULT NULL,
  `ID_Empresa` int DEFAULT NULL,
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
  CONSTRAINT `clientes_ibfk_1` FOREIGN KEY (`ID_Empresa`) REFERENCES `empresa` (`ID_Empresa`),
  CONSTRAINT `clientes_ibfk_2` FOREIGN KEY (`ID_Usuario_Creacion`) REFERENCES `usuarios` (`ID_Usuario`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `clientes`
--

LOCK TABLES `clientes` WRITE;
/*!40000 ALTER TABLE `clientes` DISABLE KEYS */;
INSERT INTO `clientes` VALUES (1,'Jorges','78963251','Ticuantepe, Managua','R526582555SD',1,'ACTIVO','2025-10-31 11:03:35',1,'Comun'),(2,'Fared','85809865','bo.17 de octubreFrente a la casa de la mujer','401-160503-1006T',1,'ACTIVO','2025-10-31 16:55:21',1,'Comun'),(3,'Leonardo','785412','Guanacaste','201',1,'ACTIVO','2025-11-24 18:02:28',1,'Comun'),(4,'Jonathan','000000','00000','000000000',1,'ACTIVO','2025-12-08 23:37:27',1,'Comun'),(5,'Josue Delgado','25639874','Diriomo, Granada','789654123',1,'ACTIVO','2025-12-08 23:38:32',1,'Comun'),(6,'Jahir','7896523','Diriomo, Granada','785-632514-0001A',1,'ACTIVO','2025-12-26 11:01:27',1,'Comun'),(7,'Clientes Varios','none','none','000000001',1,'ACTIVO','2025-12-30 15:13:17',1,'Comun'),(8,'Kenny','78965412','Blufields','7878956321478',1,'ACTIVO','2026-01-16 10:32:45',1,'Especial'),(9,'Jeshua','78963254','Matagalpa','45631235874',1,'ACTIVO','2026-01-16 10:33:52',1,'Comun'),(10,'Julio','78963254','Managua, carretera norte','7895542366',1,'ACTIVO','2026-01-16 10:44:20',1,'Especial'),(11,'Agroservicios','7454545454','frente al parque costado norte','78965412',1,'ACTIVO','2026-01-16 14:46:00',1,'Especial');
/*!40000 ALTER TABLE `clientes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `config_visibilidad_categorias`
--

DROP TABLE IF EXISTS `config_visibilidad_categorias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=122 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `config_visibilidad_categorias`
--

LOCK TABLES `config_visibilidad_categorias` WRITE;
/*!40000 ALTER TABLE `config_visibilidad_categorias` DISABLE KEYS */;
INSERT INTO `config_visibilidad_categorias` VALUES (1,'Comun',4,0,'2026-01-16 13:37:01'),(2,'Comun',1,1,'2026-01-16 14:00:49'),(3,'Especial',1,0,'2026-01-16 14:00:49'),(4,'Comun',2,0,'2026-01-16 14:00:49'),(5,'Especial',2,0,'2026-01-16 14:00:49'),(6,'Comun',3,1,'2026-01-16 14:00:49'),(7,'Especial',3,0,'2026-01-16 14:00:49'),(9,'Especial',4,1,'2026-01-16 14:00:49'),(10,'Comun',5,0,'2026-01-16 14:00:49'),(11,'Especial',5,0,'2026-01-16 14:00:49'),(12,'Comun',6,0,'2026-01-16 14:00:49'),(13,'Especial',6,0,'2026-01-16 14:00:49'),(14,'Comun',7,1,'2026-01-16 14:00:49'),(15,'Especial',7,1,'2026-01-16 14:00:49'),(16,'Comun',8,0,'2026-01-16 14:00:49'),(17,'Especial',8,0,'2026-01-16 14:00:49'),(18,'Comun',9,0,'2026-01-16 14:00:49'),(19,'Especial',9,0,'2026-01-16 14:00:49'),(20,'Comun',10,0,'2026-01-16 14:00:49'),(21,'Especial',10,0,'2026-01-16 14:00:49'),(22,'Comun',11,1,'2026-01-16 14:00:49'),(23,'Especial',11,0,'2026-01-16 14:00:49'),(24,'Comun',12,1,'2026-01-16 14:00:49'),(25,'Especial',12,0,'2026-01-16 14:00:49');
/*!40000 ALTER TABLE `config_visibilidad_categorias` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cuentas_por_cobrar`
--

DROP TABLE IF EXISTS `cuentas_por_cobrar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cuentas_por_cobrar`
--

LOCK TABLES `cuentas_por_cobrar` WRITE;
/*!40000 ALTER TABLE `cuentas_por_cobrar` DISABLE KEYS */;
INSERT INTO `cuentas_por_cobrar` VALUES (1,'2025-11-23',2,'FAC-000006','asd','2025-12-23',1,800.00,1,0.00,6,1,'Pagada'),(2,'2025-11-23',2,'FAC-000007','Venta a crédito FAC-000007','2025-12-23',1,160.00,1,0.00,7,1,'Pagada'),(3,'2025-11-23',2,'FAC-000008','Venta a crédito FAC-000008','2025-12-23',1,140.00,1,0.00,8,1,'Pagada'),(4,'2025-11-24',2,'FAC-000014','primera prueba','2025-12-24',1,900.00,1,0.00,14,1,'Pagada'),(5,'2025-11-24',2,'FAC-00016','ninguno','2025-12-24',1,6240.00,1,0.00,16,1,'Pagada'),(6,'2025-11-24',2,'FAC-00019','prueba_4','2025-12-24',1,640.00,1,0.00,19,1,'Pagada'),(7,'2025-11-24',1,'FAC-00020','prueba_5','2025-12-24',1,1620.00,1,810.00,20,1,'Vencida'),(8,'2025-11-24',1,'FAC-00021','Prueba_6_Debbug','2025-12-24',1,1440.00,1,1440.00,21,1,'Pendiente'),(9,'2025-11-24',2,'FAC-00022','prueba_8','2025-12-24',1,1600.00,1,1600.00,22,1,'Pendiente'),(10,'2025-11-24',3,'FAC-00027','pruebaaas_6','2025-12-24',1,1800.00,1,1800.00,27,1,'Pendiente'),(11,'2025-11-24',2,'FAC-00032','primera pueba','2025-12-24',1,1440.00,1,1440.00,32,1,'Pendiente'),(12,'2025-11-25',1,'FAC-00040','Venta a crédito','2025-12-25',1,1800.00,1,1800.00,40,1,'Pendiente'),(13,'2025-11-25',3,'FAC-00052','Venta a crédito','2025-12-25',1,21128.50,1,10128.00,52,1,'Pendiente'),(14,'2025-11-25',2,'FAC-00053','prueba desde mobile','2025-12-25',1,5700.00,1,5700.00,53,1,'Pendiente'),(15,'2025-11-25',3,'FAC-00054','segunda prueba','2025-12-25',1,5700.00,1,5700.00,54,1,'Pendiente'),(16,'2025-11-25',2,'FAC-00056','hjhjklñlkjhgfdssdfghjklñ','2025-12-25',1,10200.00,1,3200.00,56,1,'Vencida'),(17,'2025-11-25',2,'FAC-00057','prueba','2025-12-25',1,1760.00,1,0.00,57,1,'Pagada'),(18,'2025-11-25',3,'FAC-00059','Prueba dos con fecha correcta de factura','2025-12-25',1,1600.00,1,0.00,59,1,'Pagada'),(19,'2025-12-03',2,'FAC-00061','Ninguno','2026-01-02',1,3200.00,1,0.00,61,1,'Pagada'),(20,'2025-12-12',5,'FAC-00072','pruebas','2026-01-11',1,19000.00,1,0.00,72,4,'Pagada'),(21,'2025-12-23',5,'FAC-00074','Venta a crédito | ANULADA: Anulación por usuario','2026-01-22',1,1800.00,1,0.00,74,4,'Anulada'),(22,'2025-12-23',2,'FAC-00075','Venta a crédito | ANULADA: Anulación por usuario','2026-01-22',1,19500.00,1,0.00,75,1,'Anulada'),(23,'2025-12-24',5,'FAC-00078','Venta a crédito','2026-01-23',1,1900.00,1,0.00,78,1,'Pagada'),(24,'2025-12-24',2,'FAC-00082','Venta a crédito | ANULADA: adasdasdasd','2026-01-23',1,19500.00,1,0.00,82,1,'Anulada'),(25,'2025-12-24',1,'FAC-00084','Venta a crédito | ANULADA: fdgsdfgsdfg','2026-01-23',1,19500.00,1,0.00,84,1,'Anulada'),(26,'2025-12-26',4,'FAC-00085','Venta a crédito | ANULADA: dfsfsdfsdfsd','2026-01-25',1,19500.00,1,0.00,85,1,'Anulada'),(27,'2026-01-09',7,'FAC-00126','Venta a crédito','2026-02-08',1,20000.00,1,20000.00,126,1,'Pendiente'),(28,'2026-01-19',11,'FAC-00149','Venta a crédito','2026-02-18',1,2140.00,1,2140.00,149,8,'Pendiente'),(29,'2026-01-19',5,'FAC-00151','Venta a crédito','2026-02-18',1,2200.00,1,2200.00,151,8,'Pendiente');
/*!40000 ALTER TABLE `cuentas_por_cobrar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cuentas_por_pagar`
--

DROP TABLE IF EXISTS `cuentas_por_pagar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cuentas_por_pagar`
--

LOCK TABLES `cuentas_por_pagar` WRITE;
/*!40000 ALTER TABLE `cuentas_por_pagar` DISABLE KEYS */;
INSERT INTO `cuentas_por_pagar` VALUES (1,9,'2025-11-14',1,'prueba_9','niceee madafackas','2025-12-14',1,21000.00,1,0.00,1,'Pagada'),(2,10,'2025-11-14',1,'prueba_10','ninguno','2025-12-14',1,18000.00,1,0.00,1,'Pagada'),(3,11,'2025-11-14',1,'prueba_11','lioncu','2025-12-14',1,24000.00,1,0.00,1,'Pagada'),(4,12,'2025-11-14',1,'prueba_11','nada','2025-12-14',1,17000.00,1,10000.00,1,'Pendiente'),(5,15,'2025-11-15',1,'prueba_43','dasdasd','2025-12-15',1,2700.00,1,2700.00,1,'Pendiente'),(6,100,'2025-12-20',1,'','Compra a crédito','2026-01-19',1,152000.00,1,152000.00,4,'Pendiente'),(7,104,'2025-12-22',1,'','Compra a crédito','2026-01-21',1,12800.00,1,12800.00,4,'Pendiente'),(8,106,'2025-12-23',1,'Prueba_111','Compra a crédito | ANULADA %d/%m/%Y %H:%i - Compra #106','2026-01-22',1,1440.00,1,0.00,4,'Anulada'),(9,108,'2025-12-23',1,'','Compra a crédito | ANULADA %d/%m/%Y %H:%i - Compra #108','2026-01-22',1,1440.00,1,0.00,4,'Anulada');
/*!40000 ALTER TABLE `cuentas_por_pagar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `detalle_facturacion`
--

DROP TABLE IF EXISTS `detalle_facturacion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=218 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `detalle_facturacion`
--

LOCK TABLES `detalle_facturacion` WRITE;
/*!40000 ALTER TABLE `detalle_facturacion` DISABLE KEYS */;
INSERT INTO `detalle_facturacion` VALUES (1,4,5,50.00,180.00,9000.00),(2,5,5,2.00,180.00,360.00),(3,6,2,5.00,160.00,800.00),(4,7,3,1.00,160.00,160.00),(5,8,4,1.00,140.00,140.00),(6,9,5,20.00,180.00,3600.00),(7,9,3,10.00,160.00,1600.00),(8,9,4,6.00,140.00,840.00),(9,10,2,1.00,160.00,160.00),(10,11,2,4.00,160.00,640.00),(11,12,2,5.00,160.00,800.00),(12,13,5,10.00,180.00,1800.00),(13,14,5,5.00,180.00,900.00),(14,15,2,1.00,160.00,160.00),(15,16,3,39.00,160.00,6240.00),(16,17,3,1.00,160.00,160.00),(17,17,5,1.00,180.00,180.00),(18,18,3,1.00,160.00,160.00),(19,19,2,4.00,160.00,640.00),(20,20,5,9.00,180.00,1620.00),(21,21,3,8.00,180.00,1440.00),(22,22,2,10.00,160.00,1600.00),(23,26,5,20.00,180.00,3600.00),(24,27,2,10.00,180.00,1800.00),(25,30,5,10.00,180.00,1800.00),(26,30,2,10.00,160.00,1600.00),(27,31,5,1.00,180.00,180.00),(28,31,5,1.00,180.00,180.00),(29,32,5,8.00,180.00,1440.00),(30,33,5,10.00,180.00,1800.00),(31,35,5,10.00,180.00,1800.00),(32,36,2,50.00,160.00,8000.00),(33,37,5,20.00,180.00,3600.00),(34,37,2,10.00,160.00,1600.00),(35,40,5,10.00,180.00,1800.00),(36,44,2,10.00,180.00,1800.00),(37,46,2,30.00,180.00,5400.00),(38,47,2,10.00,160.00,1600.00),(39,48,2,10.00,160.00,1600.00),(40,49,2,10.00,160.00,1600.00),(41,50,2,10.00,160.00,1600.00),(42,51,2,26.00,160.00,4160.00),(43,52,7,10.15,190.00,1928.50),(44,52,2,100.00,160.00,16000.00),(45,52,3,20.00,160.00,3200.00),(46,53,7,30.00,190.00,5700.00),(47,54,7,30.00,190.00,5700.00),(48,55,2,20.00,160.00,3200.00),(49,56,2,20.00,160.00,3200.00),(50,56,7,20.00,190.00,3800.00),(51,56,3,20.00,160.00,3200.00),(52,57,3,11.00,160.00,1760.00),(53,58,2,10.00,190.00,1900.00),(54,59,2,10.00,160.00,1600.00),(55,60,7,5.00,190.00,950.00),(56,61,2,20.00,160.00,3200.00),(57,62,2,1.00,160.00,160.00),(58,63,7,5.00,190.00,950.00),(59,64,9,10.00,1500.00,15000.00),(60,65,2,10.00,160.00,1600.00),(61,66,8,100.00,130.00,13000.00),(62,67,5,50.00,180.00,9000.00),(63,68,7,1.00,190.00,190.00),(64,69,7,1.00,190.00,190.00),(65,70,5,25.00,180.00,4500.00),(66,71,2,9.00,180.00,1620.00),(67,72,7,100.00,190.00,19000.00),(68,73,9,10.00,1500.00,15000.00),(69,74,5,10.00,180.00,1800.00),(70,75,5,100.00,195.00,19500.00),(71,76,5,10.00,180.00,1800.00),(72,77,5,10.00,180.00,1800.00),(73,78,5,10.00,190.00,1900.00),(74,79,5,10.00,195.00,1950.00),(75,80,5,10.00,180.00,1800.00),(76,81,5,100.00,180.00,18000.00),(77,82,5,100.00,195.00,19500.00),(78,83,5,100.00,195.00,19500.00),(79,84,5,100.00,195.00,19500.00),(80,85,5,100.00,195.00,19500.00),(81,86,5,100.00,195.00,19500.00),(82,87,5,100.00,195.00,19500.00),(83,88,3,100.00,160.00,16000.00),(84,89,8,100.00,140.00,14000.00),(85,90,5,100.00,195.00,19500.00),(86,91,5,30.00,195.00,5850.00),(87,91,2,10.00,160.00,1600.00),(88,92,5,10.00,195.00,1950.00),(89,93,2,190.00,160.00,30400.00),(90,94,8,100.00,165.00,16500.00),(91,95,5,100.00,195.00,19500.00),(92,96,5,60.00,195.00,11700.00),(93,97,5,10.00,195.00,1950.00),(94,98,5,10.00,195.00,1950.00),(95,99,7,11.00,200.00,2200.00),(96,100,7,10.00,200.00,2000.00),(97,101,5,10.00,195.00,1950.00),(98,102,8,2.00,130.00,260.00),(99,103,8,1.00,195.00,195.00),(100,104,7,1.00,200.00,200.00),(101,105,5,10.00,200.00,2000.00),(102,106,5,10.00,200.00,2000.00),(103,107,5,1.00,200.00,200.00),(104,108,5,19.00,200.00,3800.00),(105,109,5,850.00,200.00,170000.00),(106,110,7,190.00,200.00,38000.00),(107,111,7,10.00,200.00,2000.00),(108,112,7,10.00,200.00,2000.00),(109,113,7,120.00,200.00,24000.00),(110,113,11,120.00,0.00,0.00),(111,114,7,1.00,200.00,200.00),(112,114,11,1.00,0.00,0.00),(113,115,12,5.00,1250.00,6250.00),(114,116,11,100.00,3.50,350.00),(115,116,7,10.00,200.00,2000.00),(116,116,11,10.00,0.00,0.00),(117,117,11,50.00,3.50,175.00),(118,117,10,9.00,190.00,1710.00),(119,117,11,9.00,0.00,0.00),(120,118,12,3.00,1250.00,3750.00),(121,118,7,29.00,200.00,5800.00),(122,118,11,100.00,3.50,350.00),(123,118,11,31.00,0.00,0.00),(124,119,12,5.00,1250.00,6250.00),(125,119,10,30.00,190.00,5700.00),(126,119,11,33.00,0.00,0.00),(127,120,11,100.00,200.00,20000.00),(128,120,7,10.00,200.00,2000.00),(129,120,11,11.00,0.00,0.00),(130,121,7,10.00,200.00,2000.00),(131,121,11,11.00,0.00,0.00),(132,122,7,1.00,200.00,200.00),(133,122,11,1.00,0.00,0.00),(134,123,10,1.00,190.00,190.00),(135,123,11,1.00,0.00,0.00),(136,124,5,10.00,200.00,2000.00),(137,124,11,11.00,0.00,0.00),(138,125,5,10.00,200.00,2000.00),(139,125,11,11.00,0.00,0.00),(140,126,5,100.00,200.00,20000.00),(141,126,11,110.00,0.00,0.00),(142,127,11,100.00,3.50,350.00),(143,127,5,100.00,200.00,20000.00),(144,127,12,5.00,1250.00,6250.00),(145,127,11,110.00,0.00,0.00),(146,128,5,10.00,200.00,2000.00),(147,128,11,11.00,0.00,0.00),(148,129,5,10.00,200.00,2000.00),(149,129,8,20.00,130.00,2600.00),(150,129,11,33.00,0.00,0.00),(151,130,5,4.00,160.00,640.00),(152,130,11,4.00,0.00,0.00),(153,131,8,1.00,165.00,165.00),(154,131,11,1.00,0.00,0.00),(155,132,2,2.00,195.00,390.00),(156,132,11,2.00,0.00,0.00),(157,133,3,30.00,180.00,5400.00),(158,133,11,33.00,0.00,0.00),(159,134,2,1.00,190.00,190.00),(160,134,11,1.00,0.00,0.00),(161,135,7,1.00,200.00,200.00),(162,135,11,1.00,0.00,0.00),(163,136,2,10.00,190.00,1900.00),(164,136,11,11.00,0.00,0.00),(165,137,5,1.00,200.00,200.00),(166,137,11,1.00,0.00,0.00),(167,138,13,2.00,70.00,140.00),(168,139,7,12.00,200.00,2400.00),(169,139,11,13.00,0.00,0.00),(170,140,14,3.00,1070.00,3210.00),(171,140,12,5.00,1250.00,6250.00),(172,141,14,3.00,1070.00,3210.00),(173,141,12,5.00,1250.00,6250.00),(174,142,5,10.00,200.00,2000.00),(175,142,13,6.00,70.00,420.00),(176,142,11,100.00,3.50,350.00),(177,142,11,11.00,0.00,0.00),(178,143,10,10.00,190.00,1900.00),(179,143,11,11.00,0.00,0.00),(180,144,14,6.00,1070.00,6420.00),(181,145,12,6.00,1070.00,6420.00),(182,146,14,2.00,1070.00,2140.00),(183,146,12,3.00,3.50,10.50),(184,147,7,200.00,200.00,40000.00),(185,147,11,220.00,0.00,0.00),(186,148,12,1.00,1250.00,1250.00),(187,148,14,2.00,1070.00,2140.00),(188,149,14,2.00,1070.00,2140.00),(189,150,5,10.00,200.00,2000.00),(190,150,11,11.00,0.00,0.00),(191,151,7,11.00,200.00,2200.00),(192,151,11,12.00,0.00,0.00),(193,152,5,20.00,200.00,4000.00),(194,152,11,22.00,0.00,0.00),(195,153,11,100.00,1070.00,107000.00),(196,154,14,1.00,1070.00,1070.00),(197,155,14,1.00,1070.00,1070.00),(198,156,14,1.00,1070.00,1070.00),(199,157,12,2.00,1250.00,2500.00),(200,158,5,10.00,200.00,2000.00),(201,158,11,11.00,0.00,0.00),(202,159,5,10.00,200.00,2000.00),(203,159,7,10.00,200.00,2000.00),(204,159,11,22.00,0.00,0.00),(205,160,14,3.00,1070.00,3210.00),(206,161,14,10.00,1070.00,10700.00),(207,162,5,2.00,200.00,400.00),(208,162,11,2.00,0.00,0.00),(209,163,14,1.00,1070.00,1070.00),(210,163,12,1.00,1250.00,1250.00),(211,164,14,1.00,1070.00,1070.00),(212,164,12,1.00,1250.00,1250.00),(213,165,5,5.00,200.00,1000.00),(214,165,10,5.00,190.00,950.00),(215,165,3,5.00,160.00,800.00),(216,165,11,16.00,0.00,0.00),(217,166,13,10.00,70.00,700.00);
/*!40000 ALTER TABLE `detalle_facturacion` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `detalle_movimientos_inventario`
--

DROP TABLE IF EXISTS `detalle_movimientos_inventario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=289 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `detalle_movimientos_inventario`
--

LOCK TABLES `detalle_movimientos_inventario` WRITE;
/*!40000 ALTER TABLE `detalle_movimientos_inventario` DISABLE KEYS */;
INSERT INTO `detalle_movimientos_inventario` VALUES (2,2,1,500.00,170.00,170.00,85000.00,1,'2025-11-12 22:10:18'),(3,3,1,500.00,170.00,170.00,85000.00,1,'2025-11-13 08:35:29'),(4,4,1,200.00,140.00,140.00,28000.00,1,'2025-11-13 09:02:58'),(5,5,1,50.00,170.00,170.00,8500.00,1,'2025-11-13 09:14:52'),(6,6,2,200.00,160.00,160.00,32000.00,1,'2025-11-13 10:06:58'),(7,7,1,100.00,170.00,170.00,17000.00,1,'2025-11-13 10:08:48'),(8,7,2,100.00,160.00,160.00,16000.00,1,'2025-11-13 10:08:48'),(9,8,4,500.00,140.00,140.00,70000.00,1,'2025-11-13 23:09:30'),(10,9,4,150.00,140.00,140.00,21000.00,1,'2025-11-14 08:10:23'),(11,10,1,100.00,180.00,180.00,18000.00,1,'2025-11-14 08:12:53'),(12,11,3,150.00,160.00,160.00,24000.00,1,'2025-11-14 08:43:17'),(14,12,3,100.00,170.00,170.00,17000.00,1,'2025-11-14 11:35:57'),(22,13,1,100.00,180.00,180.00,18000.00,1,'2025-11-15 02:31:50'),(23,14,1,50.00,180.00,180.00,9000.00,1,'2025-11-15 02:32:10'),(27,17,1,35.00,170.00,0.00,5950.00,1,'2025-11-15 10:39:19'),(28,1,1,150.00,170.00,170.00,25500.00,1,'2025-11-15 10:43:26'),(29,16,4,350.00,140.00,140.00,49000.00,1,'2025-11-15 11:33:37'),(30,18,5,150.00,150.00,0.00,22500.00,1,'2025-11-15 11:43:03'),(31,19,2,5.00,0.00,160.00,800.00,1,'2025-11-23 00:19:38'),(32,20,3,1.00,0.00,160.00,160.00,1,'2025-11-23 00:37:07'),(33,21,4,1.00,0.00,140.00,140.00,1,'2025-11-23 00:50:58'),(34,22,5,20.00,0.00,180.00,3600.00,1,'2025-11-23 20:22:54'),(35,22,3,10.00,0.00,160.00,1600.00,1,'2025-11-23 20:22:54'),(36,22,4,6.00,0.00,140.00,840.00,1,'2025-11-23 20:22:54'),(37,15,5,15.00,180.00,180.00,2700.00,1,'2025-11-23 20:25:09'),(38,23,2,1.00,0.00,160.00,160.00,1,'2025-11-23 20:35:14'),(39,24,2,4.00,0.00,160.00,640.00,1,'2025-11-23 22:15:39'),(40,25,2,5.00,0.00,160.00,800.00,1,'2025-11-23 23:10:13'),(41,26,5,10.00,0.00,180.00,1800.00,1,'2025-11-23 23:28:22'),(42,27,5,5.00,0.00,180.00,900.00,1,'2025-11-23 23:31:16'),(43,28,2,1.00,0.00,160.00,160.00,1,'2025-11-23 23:46:14'),(44,45,5,100.00,126.00,150.00,12600.00,1,'2025-11-25 09:08:32'),(45,49,6,100.00,1250.00,1500.00,125000.00,1,'2025-11-25 10:18:57'),(46,62,2,100.00,140.00,160.00,14000.00,1,'2025-12-04 01:07:27'),(47,63,2,1.00,160.00,160.00,160.00,1,'2025-12-08 15:38:25'),(48,64,7,5.00,190.00,190.00,950.00,1,'2025-12-08 15:55:32'),(49,65,9,10.00,1500.00,1500.00,15000.00,1,'2025-12-08 22:04:43'),(50,66,2,10.00,160.00,160.00,1600.00,1,'2025-12-09 17:22:18'),(55,67,5,100.00,135.00,180.00,13500.00,1,'2025-12-09 20:34:37'),(56,67,7,100.00,142.50,190.00,14250.00,1,'2025-12-09 20:34:37'),(57,72,5,25.00,180.00,180.00,4500.00,1,'2025-12-10 17:53:06'),(58,73,2,9.00,180.00,180.00,1620.00,1,'2025-12-10 18:24:47'),(59,74,3,200.00,128.00,160.00,25600.00,1,'2025-12-10 20:29:15'),(60,75,5,10.00,144.00,180.00,1440.00,1,'2025-12-11 18:48:55'),(61,76,5,100.00,144.00,180.00,14400.00,1,'2025-12-11 18:52:01'),(62,77,5,10.00,155.00,180.00,1550.00,1,'2025-12-12 09:23:28'),(63,78,7,102.00,152.00,190.00,15504.00,4,'2025-12-12 22:26:14'),(64,79,7,100.00,190.00,190.00,19000.00,4,'2025-12-12 22:26:56'),(65,80,5,100.00,155.00,180.00,15500.00,4,'2025-12-16 09:30:21'),(66,81,9,10.00,1200.00,1500.00,12000.00,4,'2025-12-16 09:56:26'),(67,82,9,10.00,1500.00,1500.00,15000.00,4,'2025-12-16 10:50:33'),(68,83,5,100.00,155.00,180.00,15500.00,4,'2025-12-16 11:04:37'),(69,84,8,100.00,104.00,130.00,10400.00,4,'2025-12-16 11:32:09'),(70,85,5,10.00,144.00,180.00,1440.00,1,'2025-12-17 10:38:57'),(71,86,5,50.00,144.00,180.00,7200.00,1,'2025-12-17 13:28:42'),(72,87,7,10.00,152.00,190.00,1520.00,1,'2025-12-17 13:45:43'),(73,88,7,-10.00,152.00,0.00,-1520.00,1,'2025-12-17 14:17:33'),(74,89,5,100.00,144.00,180.00,14400.00,1,'2025-12-17 14:21:07'),(75,90,5,-100.00,144.00,0.00,-14400.00,1,'2025-12-17 14:24:35'),(76,91,5,115.00,144.00,180.00,16560.00,1,'2025-12-17 15:05:31'),(77,92,5,100.00,155.00,180.00,15500.00,1,'2025-12-17 15:09:24'),(78,93,5,10.00,144.00,180.00,1440.00,1,'2025-12-17 15:26:35'),(79,94,5,-10.00,144.00,0.00,-1440.00,1,'2025-12-17 15:26:49'),(80,95,5,10.00,144.00,180.00,1440.00,1,'2025-12-17 15:33:10'),(81,96,5,-10.00,144.00,0.00,-1440.00,1,'2025-12-17 15:34:29'),(82,97,7,100.00,155.00,190.00,15500.00,1,'2025-12-17 15:47:01'),(83,98,5,10.00,144.00,180.00,1440.00,4,'2025-12-20 08:21:36'),(84,99,5,-10.00,144.00,0.00,-1440.00,4,'2025-12-20 08:22:04'),(85,100,7,1000.00,152.00,190.00,152000.00,4,'2025-12-20 09:13:37'),(86,101,7,-1000.00,152.00,0.00,-152000.00,4,'2025-12-20 10:38:19'),(87,102,5,100.00,155.00,180.00,15500.00,4,'2025-12-22 11:49:13'),(88,103,8,100.00,90.00,180.00,9000.00,4,'2025-12-22 12:20:51'),(89,104,3,100.00,128.00,160.00,12800.00,4,'2025-12-22 12:49:24'),(90,105,5,10.00,144.00,180.00,1440.00,4,'2025-12-22 18:25:14'),(91,106,5,10.00,144.00,180.00,1440.00,4,'2025-12-22 18:25:43'),(92,107,5,-10.00,144.00,0.00,-1440.00,4,'2025-12-22 18:26:07'),(93,108,5,10.00,144.00,180.00,1440.00,4,'2025-12-22 18:26:55'),(94,109,5,-10.00,144.00,0.00,-1440.00,4,'2025-12-22 18:27:20'),(95,110,5,10.00,180.00,180.00,1800.00,4,'2025-12-23 00:54:36'),(96,111,5,100.00,195.00,195.00,19500.00,1,'2025-12-23 14:53:57'),(97,112,5,10.00,180.00,180.00,1800.00,1,'2025-12-23 15:26:01'),(98,113,9,10.00,1200.00,1500.00,12000.00,1,'2025-12-23 15:28:54'),(99,114,9,-10.00,1200.00,0.00,-12000.00,1,'2025-12-23 15:29:05'),(100,115,5,10.00,180.00,180.00,1800.00,1,'2025-12-24 09:58:57'),(101,116,5,10.00,180.00,180.00,1800.00,1,'2025-12-24 10:19:16'),(102,117,5,10.00,190.00,190.00,1900.00,1,'2025-12-24 10:20:17'),(103,118,5,10.00,195.00,195.00,1950.00,1,'2025-12-24 10:26:43'),(104,119,5,10.00,180.00,180.00,1800.00,1,'2025-12-24 11:00:20'),(105,120,5,10.00,180.00,180.00,1800.00,1,'2025-12-24 11:26:00'),(106,121,5,10.00,195.00,195.00,1950.00,1,'2025-12-24 11:46:33'),(107,122,5,100.00,180.00,180.00,18000.00,1,'2025-12-24 13:41:07'),(108,123,7,1.00,190.00,190.00,190.00,1,'2025-12-24 15:13:18'),(109,124,5,100.00,195.00,195.00,19500.00,1,'2025-12-24 15:16:17'),(110,125,5,100.00,195.00,195.00,19500.00,1,'2025-12-24 15:16:52'),(111,126,5,100.00,195.00,195.00,19500.00,1,'2025-12-24 15:17:30'),(112,127,5,100.00,195.00,195.00,19500.00,1,'2025-12-24 15:20:48'),(113,128,5,100.00,195.00,195.00,19500.00,1,'2025-12-24 15:21:37'),(114,129,5,100.00,195.00,195.00,19500.00,1,'2025-12-26 09:20:51'),(115,130,5,100.00,195.00,195.00,19500.00,1,'2025-12-26 09:21:15'),(116,131,5,100.00,195.00,195.00,19500.00,6,'2025-12-26 12:08:51'),(117,132,5,100.00,195.00,195.00,19500.00,6,'2025-12-26 12:15:00'),(118,133,3,100.00,160.00,160.00,16000.00,6,'2025-12-27 14:26:26'),(119,134,8,100.00,140.00,140.00,14000.00,6,'2025-12-27 15:22:20'),(120,135,5,1000.00,156.00,195.00,156000.00,6,'2025-12-29 14:19:38'),(121,135,7,1000.00,156.00,195.00,156000.00,6,'2025-12-29 14:19:38'),(122,135,2,1000.00,128.00,160.00,128000.00,6,'2025-12-29 14:19:38'),(123,135,3,1000.00,128.00,160.00,128000.00,6,'2025-12-29 14:19:38'),(124,136,5,100.00,195.00,195.00,19500.00,6,'2025-12-30 11:05:05'),(125,137,5,30.00,195.00,195.00,5850.00,6,'2025-12-30 11:25:23'),(126,137,2,10.00,160.00,160.00,1600.00,6,'2025-12-30 11:25:23'),(127,138,5,10.00,195.00,195.00,1950.00,1,'2025-12-30 11:53:31'),(128,139,2,190.00,160.00,160.00,30400.00,1,'2025-12-30 11:54:42'),(129,140,8,100.00,165.00,165.00,16500.00,6,'2025-12-30 15:14:06'),(130,141,5,100.00,195.00,195.00,19500.00,1,'2026-01-02 18:07:09'),(131,142,5,100.00,195.00,195.00,19500.00,1,'2026-01-02 18:12:45'),(132,143,5,60.00,195.00,195.00,11700.00,1,'2026-01-05 15:41:00'),(133,144,5,10.00,195.00,195.00,1950.00,1,'2026-01-05 16:39:29'),(134,145,5,10.00,195.00,195.00,1950.00,1,'2026-01-05 16:39:55'),(135,146,5,10.00,195.00,195.00,1950.00,6,'2026-01-06 08:35:53'),(136,147,7,11.00,200.00,200.00,2200.00,6,'2026-01-06 08:37:02'),(137,148,7,10.00,200.00,200.00,2000.00,6,'2026-01-06 08:38:36'),(138,149,7,10.00,200.00,200.00,2000.00,6,'2026-01-06 08:39:05'),(139,150,5,10.00,195.00,195.00,1950.00,6,'2026-01-06 08:44:04'),(140,151,5,10.00,195.00,195.00,1950.00,6,'2026-01-06 08:44:21'),(141,152,8,2.00,130.00,130.00,260.00,6,'2026-01-06 08:45:38'),(142,153,8,2.00,130.00,130.00,260.00,6,'2026-01-06 08:46:03'),(143,154,8,1.00,195.00,195.00,195.00,6,'2026-01-06 08:48:43'),(144,155,7,1.00,200.00,200.00,200.00,6,'2026-01-06 09:11:31'),(145,156,7,1.00,200.00,200.00,200.00,6,'2026-01-06 09:13:22'),(146,157,5,10.00,200.00,200.00,2000.00,6,'2026-01-06 10:52:58'),(147,158,5,10.00,200.00,200.00,2000.00,6,'2026-01-06 13:42:30'),(148,159,10,1000.00,140.00,200.00,140000.00,6,'2026-01-06 13:50:37'),(149,160,5,1.00,200.00,200.00,200.00,6,'2026-01-06 14:41:34'),(150,161,5,19.00,200.00,200.00,3800.00,6,'2026-01-07 08:13:21'),(151,162,5,850.00,200.00,200.00,170000.00,6,'2026-01-07 13:39:07'),(152,163,7,190.00,200.00,200.00,38000.00,6,'2026-01-07 13:40:53'),(153,164,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 14:03:29'),(154,165,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 14:08:44'),(155,166,7,120.00,200.00,200.00,24000.00,1,'2026-01-07 14:12:27'),(156,166,11,120.00,0.00,0.00,0.00,1,'2026-01-07 14:12:27'),(157,167,7,1.00,200.00,200.00,200.00,1,'2026-01-07 14:13:28'),(158,167,11,1.00,0.00,0.00,0.00,1,'2026-01-07 14:13:28'),(159,168,12,5.00,1250.00,1250.00,6250.00,1,'2026-01-07 14:21:35'),(160,169,11,100.00,3.50,3.50,350.00,1,'2026-01-07 15:07:01'),(161,169,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 15:07:01'),(162,169,11,10.00,0.00,0.00,0.00,1,'2026-01-07 15:07:01'),(163,170,11,50.00,3.50,3.50,175.00,1,'2026-01-07 15:16:57'),(164,170,10,9.00,190.00,190.00,1710.00,1,'2026-01-07 15:16:57'),(165,170,11,9.00,0.00,0.00,0.00,1,'2026-01-07 15:16:57'),(166,171,12,3.00,1250.00,1250.00,3750.00,1,'2026-01-07 15:37:00'),(167,171,7,29.00,200.00,200.00,5800.00,1,'2026-01-07 15:37:00'),(168,171,11,100.00,3.50,3.50,350.00,1,'2026-01-07 15:37:00'),(169,171,11,31.00,0.00,0.00,0.00,1,'2026-01-07 15:37:00'),(170,172,12,5.00,1250.00,1250.00,6250.00,1,'2026-01-07 15:46:12'),(171,172,10,30.00,190.00,190.00,5700.00,1,'2026-01-07 15:46:12'),(172,172,11,33.00,0.00,0.00,0.00,1,'2026-01-07 15:46:12'),(173,173,11,100.00,200.00,200.00,20000.00,1,'2026-01-07 15:50:27'),(174,173,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 15:50:27'),(175,173,11,11.00,0.00,0.00,0.00,1,'2026-01-07 15:50:27'),(176,174,11,100.00,200.00,200.00,20000.00,1,'2026-01-07 15:51:16'),(177,174,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 15:51:16'),(178,174,11,11.00,0.00,0.00,0.00,1,'2026-01-07 15:51:16'),(179,175,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 16:14:59'),(180,175,11,11.00,0.00,0.00,0.00,1,'2026-01-07 16:14:59'),(181,176,7,10.00,200.00,200.00,2000.00,1,'2026-01-07 16:15:30'),(182,176,11,11.00,0.00,0.00,0.00,1,'2026-01-07 16:15:30'),(183,177,7,1.00,200.00,200.00,200.00,1,'2026-01-08 09:04:30'),(184,177,11,1.00,0.00,0.00,0.00,1,'2026-01-08 09:04:30'),(185,178,7,1.00,200.00,200.00,200.00,1,'2026-01-08 09:05:07'),(186,178,11,1.00,0.00,0.00,0.00,1,'2026-01-08 09:05:07'),(187,179,10,1.00,190.00,190.00,190.00,1,'2026-01-08 09:19:35'),(188,179,11,1.00,0.00,0.00,0.00,1,'2026-01-08 09:19:35'),(189,180,10,1.00,190.00,190.00,190.00,1,'2026-01-08 09:21:00'),(190,180,11,1.00,0.00,0.00,0.00,1,'2026-01-08 09:21:00'),(191,181,11,2000.00,2.80,3.50,5600.00,1,'2026-01-08 10:07:44'),(192,182,5,1000.00,160.00,200.00,160000.00,1,'2026-01-09 10:07:36'),(193,183,5,10.00,200.00,200.00,2000.00,1,'2026-01-09 13:26:51'),(194,183,11,11.00,0.00,0.00,0.00,1,'2026-01-09 13:26:51'),(195,184,7,27.00,156.00,200.00,4212.00,1,'2026-01-09 14:38:25'),(196,185,5,10.00,200.00,200.00,2000.00,1,'2026-01-09 15:16:42'),(197,185,11,11.00,0.00,0.00,0.00,1,'2026-01-09 15:16:42'),(198,186,5,100.00,200.00,200.00,20000.00,1,'2026-01-09 15:24:23'),(199,186,11,110.00,0.00,0.00,0.00,1,'2026-01-09 15:24:23'),(200,187,11,100.00,3.50,3.50,350.00,1,'2026-01-09 15:26:29'),(201,187,5,100.00,200.00,200.00,20000.00,1,'2026-01-09 15:26:29'),(202,187,12,5.00,1250.00,1250.00,6250.00,1,'2026-01-09 15:26:29'),(203,187,11,110.00,0.00,0.00,0.00,1,'2026-01-09 15:26:29'),(204,188,12,1.00,1000.00,1250.00,1000.00,1,'2026-01-09 15:29:25'),(205,189,5,10.00,200.00,200.00,2000.00,1,'2026-01-09 15:47:28'),(206,189,11,11.00,0.00,0.00,0.00,1,'2026-01-09 15:47:28'),(207,190,12,13.00,1000.00,1250.00,13000.00,1,'2026-01-09 16:19:13'),(208,191,5,10.00,200.00,200.00,2000.00,1,'2026-01-10 10:16:25'),(209,191,8,20.00,130.00,130.00,2600.00,1,'2026-01-10 10:16:25'),(210,191,11,33.00,0.00,0.00,0.00,1,'2026-01-10 10:16:25'),(211,192,5,4.00,160.00,160.00,640.00,1,'2026-01-13 09:51:13'),(212,192,11,4.00,0.00,0.00,0.00,1,'2026-01-13 09:51:13'),(213,193,8,1.00,165.00,165.00,165.00,1,'2026-01-13 09:51:48'),(214,193,11,1.00,0.00,0.00,0.00,1,'2026-01-13 09:51:48'),(215,194,2,2.00,195.00,195.00,390.00,1,'2026-01-13 11:28:28'),(216,194,11,2.00,0.00,0.00,0.00,1,'2026-01-13 11:28:28'),(217,195,3,30.00,180.00,180.00,5400.00,1,'2026-01-13 11:56:40'),(218,195,11,33.00,0.00,0.00,0.00,1,'2026-01-13 11:56:40'),(219,196,2,1.00,190.00,190.00,190.00,1,'2026-01-13 14:36:42'),(220,196,11,1.00,0.00,0.00,0.00,1,'2026-01-13 14:36:42'),(221,197,7,1.00,200.00,200.00,200.00,1,'2026-01-13 15:28:20'),(222,197,11,1.00,0.00,0.00,0.00,1,'2026-01-13 15:28:20'),(223,198,2,10.00,190.00,190.00,1900.00,1,'2026-01-13 16:04:55'),(224,198,11,11.00,0.00,0.00,0.00,1,'2026-01-13 16:04:55'),(225,199,5,1.00,200.00,200.00,200.00,1,'2026-01-14 14:22:28'),(226,199,11,1.00,0.00,0.00,0.00,1,'2026-01-14 14:22:28'),(227,200,13,1.00,0.00,70.00,0.00,1,'2026-01-14 14:41:18'),(228,201,13,100.00,0.00,70.00,0.00,1,'2026-01-14 14:42:36'),(229,202,13,56.00,0.00,70.00,0.00,1,'2026-01-14 14:59:35'),(230,203,13,2.00,70.00,70.00,140.00,1,'2026-01-14 15:00:46'),(231,204,5,20.00,0.00,200.00,0.00,1,'2026-01-14 15:19:30'),(232,205,7,12.00,200.00,200.00,2400.00,1,'2026-01-14 15:20:06'),(233,205,11,13.00,0.00,0.00,0.00,1,'2026-01-14 15:20:06'),(234,206,5,10.00,200.00,200.00,2000.00,1,'2026-01-16 15:17:49'),(235,206,13,6.00,70.00,70.00,420.00,1,'2026-01-16 15:17:49'),(236,206,11,100.00,3.50,3.50,350.00,1,'2026-01-16 15:17:49'),(237,206,11,11.00,0.00,0.00,0.00,1,'2026-01-16 15:17:49'),(238,207,10,10.00,190.00,190.00,1900.00,1,'2026-01-16 15:27:25'),(239,207,11,11.00,0.00,0.00,0.00,1,'2026-01-16 15:27:25'),(240,208,14,6.00,1070.00,1070.00,6420.00,1,'2026-01-16 15:41:10'),(241,209,12,6.00,1070.00,1070.00,6420.00,1,'2026-01-17 08:23:30'),(242,210,14,2.00,1070.00,1070.00,2140.00,1,'2026-01-17 08:40:28'),(243,210,12,3.00,3.50,3.50,10.50,1,'2026-01-17 08:40:28'),(244,211,13,30.00,0.00,70.00,0.00,8,'2026-01-17 11:05:55'),(245,212,5,15.00,0.00,200.00,0.00,8,'2026-01-17 11:10:43'),(246,213,7,200.00,200.00,200.00,40000.00,8,'2026-01-17 11:19:05'),(247,213,11,220.00,0.00,0.00,0.00,8,'2026-01-17 11:19:05'),(248,214,12,1.00,1250.00,1250.00,1250.00,8,'2026-01-17 11:23:38'),(249,214,14,2.00,1070.00,1070.00,2140.00,8,'2026-01-17 11:23:38'),(250,215,14,2.00,1070.00,1070.00,2140.00,8,'2026-01-19 08:44:58'),(251,216,5,10.00,200.00,200.00,2000.00,8,'2026-01-19 09:30:58'),(252,216,11,11.00,0.00,0.00,0.00,8,'2026-01-19 09:30:58'),(253,217,7,11.00,200.00,200.00,2200.00,8,'2026-01-19 09:31:21'),(254,217,11,12.00,0.00,0.00,0.00,8,'2026-01-19 09:31:21'),(255,218,14,23.00,856.00,1070.00,19688.00,1,'2026-01-19 11:07:44'),(256,219,5,20.00,200.00,200.00,4000.00,2,'2026-01-19 11:13:14'),(257,219,11,22.00,0.00,0.00,0.00,2,'2026-01-19 11:13:14'),(258,220,11,100.00,1070.00,1070.00,107000.00,2,'2026-01-19 11:14:30'),(259,221,14,1.00,1070.00,1070.00,1070.00,2,'2026-01-19 12:04:55'),(260,222,14,1.00,1070.00,1070.00,1070.00,2,'2026-01-19 15:52:45'),(261,223,14,1.00,1070.00,1070.00,1070.00,2,'2026-01-19 15:53:27'),(262,224,12,2.00,1250.00,1250.00,2500.00,2,'2026-01-19 15:54:39'),(263,225,5,10.00,200.00,200.00,2000.00,2,'2026-01-19 15:56:58'),(264,225,11,11.00,0.00,0.00,0.00,2,'2026-01-19 15:56:58'),(265,226,5,10.00,200.00,200.00,2000.00,2,'2026-01-19 15:58:05'),(266,226,7,10.00,200.00,200.00,2000.00,2,'2026-01-19 15:58:05'),(267,226,11,22.00,0.00,0.00,0.00,2,'2026-01-19 15:58:05'),(268,227,12,50.00,1000.00,1250.00,50000.00,1,'2026-01-19 16:06:48'),(269,227,14,30.00,856.00,1070.00,25680.00,1,'2026-01-19 16:06:48'),(270,228,14,8.00,856.00,1070.00,6848.00,2,'2026-01-19 16:07:50'),(271,229,14,3.00,1070.00,1070.00,3210.00,2,'2026-01-20 08:21:12'),(272,230,8,30.00,104.00,130.00,3120.00,1,'2026-01-20 10:53:00'),(273,231,15,100.00,0.00,60.00,0.00,1,'2026-01-21 08:52:08'),(274,232,14,10.00,1070.00,1070.00,10700.00,2,'2026-01-21 09:01:19'),(275,233,5,2.00,200.00,200.00,400.00,8,'2026-01-22 16:03:12'),(276,233,11,2.00,0.00,0.00,0.00,8,'2026-01-22 16:03:12'),(277,234,14,1.00,1070.00,1070.00,1070.00,8,'2026-01-23 11:02:52'),(278,234,12,1.00,1250.00,1250.00,1250.00,8,'2026-01-23 11:02:52'),(279,235,14,1.00,1070.00,1070.00,1070.00,8,'2026-01-23 11:26:21'),(280,235,12,1.00,1250.00,1250.00,1250.00,8,'2026-01-23 11:26:21'),(281,236,5,5.00,200.00,200.00,1000.00,2,'2026-01-23 14:25:13'),(282,236,10,5.00,190.00,190.00,950.00,2,'2026-01-23 14:25:13'),(283,236,3,5.00,160.00,160.00,800.00,2,'2026-01-23 14:25:13'),(284,236,11,16.00,0.00,0.00,0.00,2,'2026-01-23 14:25:13'),(285,237,5,100.00,160.00,200.00,16000.00,2,'2026-01-23 15:24:32'),(286,237,10,100.00,152.00,190.00,15200.00,2,'2026-01-23 15:24:33'),(287,237,3,100.00,128.00,160.00,12800.00,2,'2026-01-23 15:24:33'),(288,238,13,10.00,70.00,70.00,700.00,1,'2026-01-24 09:27:47');
/*!40000 ALTER TABLE `detalle_movimientos_inventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `detalle_pedidos`
--

DROP TABLE IF EXISTS `detalle_pedidos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `detalle_pedidos`
--

LOCK TABLES `detalle_pedidos` WRITE;
/*!40000 ALTER TABLE `detalle_pedidos` DISABLE KEYS */;
INSERT INTO `detalle_pedidos` VALUES (1,1,14,1070.00,2.00,2140.00,'2026-01-21 09:20:39'),(2,1,12,1250.00,3.00,3750.00,'2026-01-21 09:20:39'),(3,2,14,1070.00,2.00,2140.00,'2026-01-21 09:20:42'),(4,2,12,1250.00,3.00,3750.00,'2026-01-21 09:20:42'),(5,3,5,200.00,10.00,2000.00,'2026-01-21 09:43:48'),(6,4,5,200.00,1.00,200.00,'2026-01-21 10:58:01'),(7,4,2,190.00,1.00,190.00,'2026-01-21 10:58:01'),(8,5,12,1250.00,11.00,13750.00,'2026-01-21 14:23:12'),(9,6,5,200.00,10.00,2000.00,'2026-01-21 15:27:22'),(10,7,5,200.00,1.00,200.00,'2026-01-21 15:28:34'),(11,8,5,200.00,2.00,400.00,'2026-01-22 08:28:57'),(12,9,14,1070.00,1.00,1070.00,'2026-01-23 11:01:55'),(13,9,12,1250.00,1.00,1250.00,'2026-01-23 11:01:55'),(14,10,5,200.00,5.00,1000.00,'2026-01-23 13:45:40'),(15,10,10,190.00,5.00,950.00,'2026-01-23 13:45:40'),(16,10,3,160.00,5.00,800.00,'2026-01-23 13:45:40'),(17,11,14,1070.00,6.00,6420.00,'2026-01-23 14:39:51'),(18,11,12,1250.00,4.00,5000.00,'2026-01-23 14:39:51');
/*!40000 ALTER TABLE `detalle_pedidos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `empresa`
--

DROP TABLE IF EXISTS `empresa`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `empresa`
--

LOCK TABLES `empresa` WRITE;
/*!40000 ALTER TABLE `empresa` DISABLE KEYS */;
INSERT INTO `empresa` VALUES (1,'Granja Avicola FERDEL','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U'),(2,'Cerdos','Rastro Municipal 150 mts. Norte, Diriomo','81006837','Activo','2031407850000U');
/*!40000 ALTER TABLE `empresa` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `facturacion`
--

DROP TABLE IF EXISTS `facturacion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=167 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `facturacion`
--

LOCK TABLES `facturacion` WRITE;
/*!40000 ALTER TABLE `facturacion` DISABLE KEYS */;
INSERT INTO `facturacion` VALUES (1,'2025-11-23',2,NULL,'',1,1,'2025-11-22 23:06:26','Activa',NULL),(2,'2025-11-23',1,NULL,'asdfagasdf',1,1,'2025-11-23 00:03:56','Activa',NULL),(3,'2025-11-23',1,NULL,'',1,1,'2025-11-23 00:06:10','Activa',NULL),(4,'2025-11-23',1,NULL,'addfas',1,1,'2025-11-23 00:12:36','Activa',NULL),(5,'2025-11-23',2,NULL,'',1,1,'2025-11-23 00:13:18','Activa',NULL),(6,'2025-11-23',2,NULL,'asd',1,1,'2025-11-23 00:19:35','Activa',NULL),(7,'2025-11-23',2,NULL,'',1,1,'2025-11-23 00:37:04','Activa',NULL),(8,'2025-11-23',2,NULL,'',1,1,'2025-11-23 00:50:55','Activa',NULL),(9,'2025-11-24',1,NULL,'jjajaja',1,1,'2025-11-23 20:22:54','Activa',NULL),(10,'2025-11-24',1,NULL,'',1,1,'2025-11-23 20:35:14','Activa',NULL),(11,'2025-11-24',1,NULL,'',1,1,'2025-11-23 22:15:39','Activa',NULL),(12,'2025-11-24',2,NULL,'',1,1,'2025-11-23 23:10:12','Activa',NULL),(13,'2025-11-24',2,0,'',1,1,'2025-11-23 23:28:19','Activa',NULL),(14,'2025-11-24',2,1,'primera prueba',1,1,'2025-11-23 23:31:06','Activa',NULL),(15,'2025-11-24',1,0,'',1,1,'2025-11-23 23:46:12','Activa',NULL),(16,'2025-11-24',2,1,'ninguno',1,1,'2025-11-24 14:14:21','Activa',NULL),(17,'2025-11-24',2,1,'prueba_2',1,1,'2025-11-24 15:46:55','Activa',NULL),(18,'2025-11-24',2,0,'prueba_3',1,1,'2025-11-24 16:26:37','Activa',NULL),(19,'2025-11-24',2,1,'prueba_4',1,1,'2025-11-24 16:34:30','Activa',NULL),(20,'2025-11-24',1,1,'prueba_5',1,1,'2025-11-24 16:38:03','Activa',NULL),(21,'2025-11-24',1,1,'Prueba_6_Debbug',1,1,'2025-11-24 17:05:13','Activa',NULL),(22,'2025-11-24',2,1,'prueba_8',1,1,'2025-11-24 17:35:16','Activa',NULL),(23,'2025-11-24',3,0,'pruebaaa',1,1,'2025-11-24 18:31:26','Activa',NULL),(24,'2025-11-24',3,0,'pruebaaa',1,1,'2025-11-24 18:31:37','Activa',NULL),(25,'2025-11-24',3,0,'pruebaaa',1,1,'2025-11-24 18:32:03','Activa',NULL),(26,'2025-11-24',2,0,'prueba',1,1,'2025-11-24 18:33:04','Activa',NULL),(27,'2025-11-24',3,1,'pruebaaas_6',1,1,'2025-11-24 18:39:03','Activa',NULL),(28,'2025-11-24',2,0,'N/A',1,1,'2025-11-24 18:43:46','Activa',NULL),(29,'2025-11-24',2,0,'N/A',1,1,'2025-11-24 18:44:10','Activa',NULL),(30,'2025-11-24',2,0,'N/A',1,1,'2025-11-24 18:44:48','Activa',NULL),(31,'2025-11-24',3,0,'yesyes',1,1,'2025-11-24 19:37:27','Activa',NULL),(32,'2025-11-24',2,1,'primera pueba',1,1,'2025-11-24 21:42:41','Activa',NULL),(33,'2025-11-24',1,0,'',1,1,'2025-11-24 23:02:09','Activa',NULL),(34,'2025-11-24',2,0,'',1,1,'2025-11-24 23:43:19','Activa',NULL),(35,'2025-11-24',2,0,'',1,1,'2025-11-24 23:43:59','Activa',NULL),(36,'2025-11-24',2,0,'prueba de factura',1,1,'2025-11-24 23:56:32','Activa',NULL),(37,'2025-11-25',2,0,'',1,1,'2025-11-25 00:02:02','Activa',NULL),(38,'2025-11-25',2,0,'llll',1,1,'2025-11-25 00:03:07','Activa',NULL),(39,'2025-11-25',2,0,'llll',1,1,'2025-11-25 00:03:17','Activa',NULL),(40,'2025-11-25',1,1,'',1,1,'2025-11-25 00:04:27','Activa',NULL),(41,'2025-11-25',3,0,'',1,1,'2025-11-25 00:05:52','Activa',NULL),(42,'2025-11-25',2,0,'dgffghfgh',1,1,'2025-11-25 00:06:55','Activa',NULL),(43,'2025-11-25',2,0,'xxcvcxv',1,1,'2025-11-25 00:07:34','Activa',NULL),(44,'2025-11-25',2,0,'xxcvcxv',1,1,'2025-11-25 00:07:56','Activa',NULL),(45,'2025-11-25',2,0,'asdasdfasdf',1,1,'2025-11-25 09:14:38','Activa',NULL),(46,'2025-11-25',2,0,'asdasdfasdf',1,1,'2025-11-25 09:25:53','Activa',NULL),(47,'2025-11-25',2,0,'kjjbliblk',1,1,'2025-11-25 09:30:22','Activa',NULL),(48,'2025-11-25',3,0,'JAJAJA',1,1,'2025-11-25 10:08:52','Activa',NULL),(49,'2025-11-25',2,0,'dfgdfg',1,1,'2025-11-25 10:19:45','Activa',NULL),(50,'2025-11-25',3,0,'',1,1,'2025-11-25 10:26:39','Activa',NULL),(51,'2025-11-25',3,0,'prubea_uno_reemplazando bodega',1,1,'2025-11-25 12:01:41','Activa',NULL),(52,'2025-11-25',3,1,'',1,1,'2025-11-25 12:04:29','Activa',NULL),(53,'2025-11-25',2,1,'prueba desde mobile',1,1,'2025-11-25 12:10:50','Activa',NULL),(54,'2025-11-25',3,1,'segunda prueba',1,1,'2025-11-25 12:25:58','Activa',NULL),(55,'2025-11-25',2,0,'sdfg',1,1,'2025-11-25 12:51:36','Activa',NULL),(56,'2025-11-25',2,1,'hjhjklñlkjhgfdssdfghjklñ',1,1,'2025-11-25 12:56:37','Activa',NULL),(57,'2025-11-25',2,1,'prueba',1,1,'2025-11-25 15:15:43','Activa',NULL),(58,'2025-11-25',3,0,'zazxczxczxc',1,1,'2025-11-25 15:18:49','Activa',NULL),(59,'2025-11-25',3,1,'Prueba dos con fecha correcta de factura',1,1,'2025-11-25 15:20:21','Activa',NULL),(60,'2025-11-25',3,0,'dfasdasdfasdfasdfasdf',1,1,'2025-11-25 15:22:05','Activa',NULL),(61,'2025-12-03',2,1,'Ninguno',1,1,'2025-12-03 15:45:47','Activa',NULL),(62,'2025-12-08',3,0,'Ninguno',1,1,'2025-12-08 15:38:24','Activa',NULL),(63,'2025-12-08',2,0,'',1,1,'2025-12-08 15:55:29','Activa',NULL),(64,'2025-12-08',2,0,'',1,1,'2025-12-08 22:04:43','Activa',NULL),(65,'2025-12-09',2,0,'',1,1,'2025-12-09 17:22:18','Activa',NULL),(66,'2025-12-10',2,1,'',1,1,'2025-12-10 17:09:46','Activa',NULL),(67,'2025-12-10',5,1,'sdfdf',1,1,'2025-12-10 17:27:15','Activa',NULL),(68,'2025-12-10',2,0,'',1,1,'2025-12-10 17:41:50','Activa',NULL),(69,'2025-12-10',2,0,' | ANULADA: asdasdasdasda',1,1,'2025-12-10 17:42:05','Anulada',NULL),(70,'2025-12-10',2,0,'',1,1,'2025-12-10 17:53:06','Activa',NULL),(71,'2025-12-10',5,0,'',1,1,'2025-12-10 18:24:46','Activa',NULL),(72,'2025-12-12',5,1,'pruebas',1,4,'2025-12-12 22:26:56','Activa',NULL),(73,'2025-12-16',2,0,'',1,4,'2025-12-16 10:50:29','Activa',NULL),(74,'2025-12-23',5,1,' | ANULADA: Anulación por usuario',1,4,'2025-12-23 00:54:36','Anulada',NULL),(75,'2025-12-23',2,1,' | ANULADA: Anulación por usuario',1,1,'2025-12-23 14:53:56','Anulada',NULL),(76,'2025-12-23',4,0,' | ANULADA: Anulación por usuario',1,1,'2025-12-23 15:26:01','Anulada',NULL),(77,'2025-12-24',4,0,' | ANULADA: wdsfsfds',1,1,'2025-12-24 09:58:57','Anulada',NULL),(78,'2025-12-24',5,1,'',1,1,'2025-12-24 10:20:17','Activa',NULL),(79,'2025-12-24',5,0,' | ANULADA: sfsadfasdfasdf',1,1,'2025-12-24 10:26:43','Anulada',NULL),(80,'2025-12-24',5,0,' | ANULADA: porque simon',1,1,'2025-12-24 11:00:20','Anulada',NULL),(81,'2025-12-24',2,0,'',1,1,'2025-12-24 13:41:07','Activa',NULL),(82,'2025-12-24',2,1,' | ANULADA: adasdasdasd',1,1,'2025-12-24 15:16:17','Anulada',NULL),(83,'2025-12-24',4,0,'',1,1,'2025-12-24 15:17:30','Activa',NULL),(84,'2025-12-24',1,1,' | ANULADA: fdgsdfgsdfg',1,1,'2025-12-24 15:20:48','Anulada',NULL),(85,'2025-12-26',4,1,' | ANULADA: dfsfsdfsdfsd',1,1,'2025-12-26 09:20:51','Anulada',NULL),(86,'2025-12-26',6,0,'',1,6,'2025-12-26 12:08:51','Activa',NULL),(87,'2025-12-26',1,0,'',1,6,'2025-12-26 12:15:00','Activa',NULL),(88,'2025-12-27',4,0,'',1,6,'2025-12-27 14:26:26','Activa',NULL),(89,'2025-12-27',2,0,'',1,6,'2025-12-27 15:22:20','Activa',NULL),(90,'2025-12-30',6,0,'',1,6,'2025-12-30 11:05:05','Activa',NULL),(91,'2025-12-30',2,0,'',1,6,'2025-12-30 11:25:23','Activa',NULL),(92,'2025-12-30',2,0,'',1,1,'2025-12-30 11:53:31','Activa',NULL),(93,'2025-12-30',4,0,'',1,1,'2025-12-30 11:54:42','Activa',NULL),(94,'2025-12-30',7,0,'',1,6,'2025-12-30 15:14:06','Activa',NULL),(95,'2026-01-02',2,0,' | ANULADA: sipi comprendo todo',1,1,'2026-01-02 18:07:09','Anulada',NULL),(96,'2026-01-05',7,0,'',1,1,'2026-01-05 15:41:00','Activa',NULL),(97,'2026-01-05',7,0,' | ANULADA: Error en la venta',1,1,'2026-01-05 16:39:28','Anulada',NULL),(98,'2026-01-06',7,0,'',1,6,'2026-01-06 08:35:53','Activa',NULL),(99,'2026-01-06',2,0,'',1,6,'2026-01-06 08:37:02','Activa',NULL),(100,'2026-01-06',2,0,' | ANULADA: ingreso mal de datos',1,6,'2026-01-06 08:38:36','Anulada',NULL),(101,'2026-01-06',7,0,' | ANULADA: asdasdasdas',1,6,'2026-01-06 08:44:04','Anulada',NULL),(102,'2026-01-06',7,0,' | ANULADA: JAJAJAJAJA',1,6,'2026-01-06 08:45:38','Anulada',NULL),(103,'2026-01-06',7,0,'',1,6,'2026-01-06 08:48:43','Activa',NULL),(104,'2026-01-06',6,0,' | ANULADA: mal ingreso de cantidad de producto',1,6,'2026-01-06 09:11:31','Anulada',NULL),(105,'2026-01-06',7,0,'',1,6,'2026-01-06 10:52:58','Activa',NULL),(106,'2026-01-06',2,0,'',1,6,'2026-01-06 13:42:30','Activa',NULL),(107,'2026-01-06',7,0,'',1,6,'2026-01-06 14:41:34','Activa',NULL),(108,'2026-01-07',7,0,'',1,6,'2026-01-07 08:13:21','Activa',NULL),(109,'2026-01-07',7,0,'',1,6,'2026-01-07 13:39:07','Activa',NULL),(110,'2026-01-07',2,0,'',1,6,'2026-01-07 13:40:53','Activa',NULL),(111,'2026-01-07',6,0,'',1,1,'2026-01-07 14:03:29','Activa',NULL),(112,'2026-01-07',4,0,'',1,1,'2026-01-07 14:08:44','Activa',NULL),(113,'2026-01-07',4,0,' | Descontados: 120.0 separadores',1,1,'2026-01-07 14:12:27','Activa',NULL),(114,'2026-01-07',2,0,' | Descontados: 1.0 separadores',1,1,'2026-01-07 14:13:28','Activa',NULL),(115,'2026-01-07',5,0,'',1,1,'2026-01-07 14:21:35','Activa',NULL),(116,'2026-01-07',4,0,' | Descontados: 10.0 separadores',1,1,'2026-01-07 15:07:01','Activa',NULL),(117,'2026-01-07',5,0,' | Descontados: 9.0 separadores',1,1,'2026-01-07 15:16:56','Activa',NULL),(118,'2026-01-07',5,0,' | Cajillas huevos: 29.0, Separadores: 31.0 (incluye 2.0 bases extra)',1,1,'2026-01-07 15:37:00','Activa',NULL),(119,'2026-01-07',2,0,' | Cajillas huevos: 30.0, Separadores: 33.0 (incluye 3.0 bases extra)',1,1,'2026-01-07 15:46:11','Activa',NULL),(120,'2026-01-07',1,0,' | ANULADA: mal ingreso de datos',1,1,'2026-01-07 15:50:27','Anulada',NULL),(121,'2026-01-07',7,0,' | ANULADA: venta incorrecta',1,1,'2026-01-07 16:14:59','Anulada',NULL),(122,'2026-01-08',7,0,' | ANULADA: error',1,1,'2026-01-08 09:04:30','Anulada',NULL),(123,'2026-01-08',7,0,' | ANULADA: sdfsdfsdfsdf',1,1,'2026-01-08 09:19:35','Anulada',NULL),(124,'2026-01-09',7,0,'',1,1,'2026-01-09 13:26:51','Activa',NULL),(125,'2026-01-09',7,0,'',1,1,'2026-01-09 15:16:42','Activa',NULL),(126,'2026-01-09',7,1,'',1,1,'2026-01-09 15:24:23','Activa',NULL),(127,'2026-01-09',4,0,'',1,1,'2026-01-09 15:26:29','Activa',NULL),(128,'2026-01-09',2,0,'',1,1,'2026-01-09 15:47:28','Activa',NULL),(129,'2026-01-10',7,0,'',1,1,'2026-01-10 10:16:25','Activa',NULL),(130,'2026-01-13',7,0,'',1,1,'2026-01-13 09:51:13','Activa',NULL),(131,'2026-01-13',7,0,'',1,1,'2026-01-13 09:51:48','Activa',NULL),(132,'2026-01-13',7,0,'',1,1,'2026-01-13 11:28:28','Activa',NULL),(133,'2026-01-13',7,0,'',1,1,'2026-01-13 11:56:40','Activa',NULL),(134,'2026-01-13',7,0,'',1,1,'2026-01-13 14:36:42','Activa',NULL),(135,'2026-01-13',7,0,'',1,1,'2026-01-13 15:28:20','Activa',NULL),(136,'2026-01-13',7,0,'',1,1,'2026-01-13 16:04:55','Activa',NULL),(137,'2026-01-14',2,0,'',1,1,'2026-01-14 14:22:28','Activa',NULL),(138,'2026-01-14',7,0,'',1,1,'2026-01-14 15:00:46','Activa',NULL),(139,'2026-01-14',7,0,'',1,1,'2026-01-14 15:20:06','Activa',NULL),(140,'2026-01-16',11,0,'',1,1,'2026-01-16 14:58:30','Activa',NULL),(141,'2026-01-16',11,0,'',1,1,'2026-01-16 14:58:38','Activa',NULL),(142,'2026-01-16',7,0,'',1,1,'2026-01-16 15:17:49','Activa',NULL),(143,'2026-01-16',6,0,'',1,1,'2026-01-16 15:27:24','Activa',NULL),(144,'2026-01-16',11,0,'',1,1,'2026-01-16 15:41:10','Activa',NULL),(145,'2026-01-17',8,0,'',1,1,'2026-01-17 08:23:30','Activa',NULL),(146,'2026-01-17',11,0,'',1,1,'2026-01-17 08:40:28','Activa',NULL),(147,'2026-01-17',2,0,'',1,8,'2026-01-17 11:19:05','Activa',NULL),(148,'2026-01-17',8,0,'',1,8,'2026-01-17 11:23:38','Activa',NULL),(149,'2026-01-19',11,1,'',1,8,'2026-01-19 08:44:58','Activa',NULL),(150,'2026-01-19',9,0,'',1,8,'2026-01-19 09:30:58','Activa',NULL),(151,'2026-01-19',5,1,'',1,8,'2026-01-19 09:31:21','Activa',NULL),(152,'2026-01-19',5,0,'',1,2,'2026-01-19 11:13:14','Activa',NULL),(153,'2026-01-19',11,0,'',1,2,'2026-01-19 11:14:30','Activa',NULL),(154,'2026-01-19',11,0,'',1,2,'2026-01-19 12:04:55','Activa',NULL),(155,'2026-01-19',11,0,'',1,2,'2026-01-19 15:52:45','Activa',NULL),(156,'2026-01-19',11,0,'',1,2,'2026-01-19 15:53:27','Activa',NULL),(157,'2026-01-19',11,0,'',1,2,'2026-01-19 15:54:39','Activa',NULL),(158,'2026-01-19',4,0,'',1,2,'2026-01-19 15:56:58','Activa',NULL),(159,'2026-01-19',5,0,'',1,2,'2026-01-19 15:58:05','Activa',NULL),(160,'2026-01-20',11,0,'',1,2,'2026-01-20 08:21:11','Activa',NULL),(161,'2026-01-21',11,0,'',1,2,'2026-01-21 09:01:19','Activa',NULL),(162,'2026-01-22',5,0,'Pedido #8 - Sin observación',1,8,'2026-01-22 16:03:12','Activa',NULL),(163,'2026-01-23',8,0,'Pedido #9 - Sin observación',1,8,'2026-01-23 11:02:52','Activa',NULL),(164,'2026-01-23',8,0,'Pedido #9 - Sin observación',1,8,'2026-01-23 11:26:21','Activa',NULL),(165,'2026-01-23',9,0,'Pedido #10 - Sin observación',1,2,'2026-01-23 14:25:13','Activa',NULL),(166,'2026-01-24',7,0,'',1,1,'2026-01-24 09:27:47','Activa',NULL);
/*!40000 ALTER TABLE `facturacion` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `inventario_bodega`
--

DROP TABLE IF EXISTS `inventario_bodega`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `inventario_bodega`
--

LOCK TABLES `inventario_bodega` WRITE;
/*!40000 ALTER TABLE `inventario_bodega` DISABLE KEYS */;
INSERT INTO `inventario_bodega` VALUES (1,1,500.00),(1,2,986.00),(1,3,1260.00),(1,4,0.00),(1,5,794.00),(1,7,559.00),(1,8,108.00),(1,9,40.00),(1,10,1341.00),(1,11,7555.00),(1,12,30.00),(1,13,269.00),(1,14,34.00),(1,15,130.00),(1,16,300.00),(2,6,70.00);
/*!40000 ALTER TABLE `inventario_bodega` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `log_cambios_visibilidad`
--

DROP TABLE IF EXISTS `log_cambios_visibilidad`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Log de cambios en visibilidad';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `log_cambios_visibilidad`
--

LOCK TABLES `log_cambios_visibilidad` WRITE;
/*!40000 ALTER TABLE `log_cambios_visibilidad` DISABLE KEYS */;
INSERT INTO `log_cambios_visibilidad` VALUES (1,'2026-01-16 13:37:01',1,'Comun',4,NULL,1,'INSERT');
/*!40000 ALTER TABLE `log_cambios_visibilidad` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `metodos_pago`
--

DROP TABLE IF EXISTS `metodos_pago`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `metodos_pago` (
  `ID_MetodoPago` int NOT NULL AUTO_INCREMENT,
  `Nombre` varchar(255) NOT NULL,
  PRIMARY KEY (`ID_MetodoPago`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `metodos_pago`
--

LOCK TABLES `metodos_pago` WRITE;
/*!40000 ALTER TABLE `metodos_pago` DISABLE KEYS */;
INSERT INTO `metodos_pago` VALUES (1,'Efectivo'),(2,'Tarjeta'),(3,'Transferencia'),(4,'Crédito');
/*!40000 ALTER TABLE `metodos_pago` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `movimientos_inventario`
--

DROP TABLE IF EXISTS `movimientos_inventario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=239 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `movimientos_inventario`
--

LOCK TABLES `movimientos_inventario` WRITE;
/*!40000 ALTER TABLE `movimientos_inventario` DISABLE KEYS */;
INSERT INTO `movimientos_inventario` VALUES (1,1,'prueba_1',NULL,'2025-11-13',1,'CONTADO','ninhun',1,1,NULL,NULL,1,'2025-11-12 21:42:27','2025-11-15 10:43:26',1,'Activa'),(2,1,'prueba_2',NULL,'2025-11-13',1,'CONTADO','me pica el qlo',1,1,NULL,NULL,1,'2025-11-12 22:10:18',NULL,1,'Activa'),(3,1,'prueba_3',NULL,'2025-11-13',1,'CONTADO','ninguno',1,1,NULL,NULL,1,'2025-11-13 08:35:29',NULL,1,'Activa'),(4,1,'prueba_4',NULL,'2025-11-13',1,'CONTADO','ninguna al momento',1,1,NULL,NULL,1,'2025-11-13 09:02:55',NULL,1,'Activa'),(5,1,'prueba_5',NULL,'2025-11-13',1,'CONTADO','nop',1,1,NULL,NULL,1,'2025-11-13 09:13:53',NULL,1,'Activa'),(6,1,'prueba_6',NULL,'2025-11-13',1,'CONTADO','',1,1,NULL,NULL,1,'2025-11-13 10:06:58',NULL,1,'Activa'),(7,1,'prueba_7',NULL,'2025-11-13',1,'CONTADO','ninguna',1,1,NULL,NULL,1,'2025-11-13 10:08:48',NULL,1,'Activa'),(8,1,'prueba_7',NULL,'2025-11-14',1,'CONTADO','ninguno',1,1,NULL,NULL,1,'2025-11-13 23:09:30',NULL,1,'Activa'),(9,1,'prueba_9',NULL,'2025-11-14',1,'CREDITO','niceee madafackas',1,1,NULL,NULL,1,'2025-11-14 08:10:23',NULL,1,'Activa'),(10,1,'prueba_10',NULL,'2025-11-14',1,'CREDITO','ninguno',1,1,NULL,NULL,1,'2025-11-14 08:12:53',NULL,1,'Activa'),(11,1,'prueba_11',NULL,'2025-11-14',1,'CREDITO','lioncu',1,1,NULL,NULL,1,'2025-11-14 08:43:17',NULL,1,'Activa'),(12,1,'prueba_11',NULL,'2025-11-14',1,'CREDITO','nada',1,1,NULL,NULL,1,'2025-11-14 08:58:45','2025-11-14 11:35:57',1,'Activa'),(13,1,'prueba_14',NULL,'2025-11-15',1,'CONTADO','ninguno al momento',1,1,NULL,NULL,1,'2025-11-15 01:48:57','2025-11-15 02:31:50',1,'Activa'),(14,1,'prueba_15',NULL,'2025-11-15',1,'CONTADO','minguno',1,1,NULL,NULL,1,'2025-11-15 01:50:06','2025-11-15 02:32:10',1,'Activa'),(15,1,'prueba_43',NULL,'2025-11-15',1,'CREDITO','dasdasd',1,1,NULL,NULL,1,'2025-11-15 02:16:30','2025-11-23 20:25:09',1,'Activa'),(16,1,'prueba_33',NULL,'2025-11-15',1,'CONTADO','fsdfsdf',1,1,NULL,NULL,1,'2025-11-15 02:17:09','2025-11-15 11:33:37',1,'Activa'),(17,1,'prueba_34',NULL,'2025-11-15',1,'CONTADO','s',1,1,NULL,NULL,1,'2025-11-15 10:39:19',NULL,1,'Activa'),(18,1,'prueba_36',NULL,'2025-11-15',1,'CONTADO','',1,1,NULL,NULL,1,'2025-11-15 11:43:02',NULL,1,'Activa'),(19,2,NULL,6,'2025-11-23',NULL,'CREDITO','asd',1,1,NULL,NULL,1,'2025-11-23 00:19:37',NULL,NULL,'Activa'),(20,2,NULL,7,'2025-11-23',NULL,'CREDITO','',1,1,NULL,NULL,1,'2025-11-23 00:37:07',NULL,NULL,'Activa'),(21,2,NULL,8,'2025-11-23',NULL,'CREDITO','',1,1,NULL,NULL,1,'2025-11-23 00:50:56',NULL,NULL,'Activa'),(22,2,NULL,9,'2025-11-24',NULL,'CONTADO','jjajaja',1,1,NULL,NULL,1,'2025-11-23 20:22:54',NULL,NULL,'Activa'),(23,2,NULL,10,'2025-11-24',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-11-23 20:35:14',NULL,NULL,'Activa'),(24,2,NULL,11,'2025-11-24',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-11-23 22:15:39',NULL,NULL,'Activa'),(25,2,NULL,12,'2025-11-24',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-11-23 23:10:13',NULL,NULL,'Activa'),(26,2,NULL,13,'2025-11-24',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-11-23 23:28:22',NULL,NULL,'Activa'),(27,2,NULL,14,'2025-11-24',NULL,'CREDITO','primera prueba',1,1,NULL,NULL,1,'2025-11-23 23:31:15',NULL,NULL,'Activa'),(28,2,NULL,15,'2025-11-24',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-11-23 23:46:13',NULL,NULL,'Activa'),(29,2,NULL,16,'2025-11-24',NULL,'CREDITO','ninguno',1,1,NULL,NULL,1,'2025-11-24 14:14:27',NULL,NULL,'Activa'),(30,2,NULL,18,'2025-11-24',NULL,'CONTADO','prueba_3',1,1,NULL,NULL,1,'2025-11-24 16:26:38',NULL,NULL,'Activa'),(31,2,NULL,19,'2025-11-24',NULL,'CREDITO','prueba_4',1,1,NULL,NULL,1,'2025-11-24 16:34:30',NULL,NULL,'Activa'),(32,2,NULL,20,'2025-11-24',NULL,'CREDITO','prueba_5',1,1,NULL,NULL,1,'2025-11-24 16:38:04',NULL,NULL,'Activa'),(33,2,NULL,21,'2025-11-24',NULL,'CREDITO','Prueba_6_Debbug',1,1,NULL,NULL,1,'2025-11-24 17:05:14',NULL,NULL,'Activa'),(34,2,NULL,22,'2025-11-24',NULL,'CREDITO','prueba_8',1,1,NULL,NULL,1,'2025-11-24 17:35:21',NULL,NULL,'Activa'),(35,2,NULL,26,'2025-11-24',NULL,'CONTADO','prueba',1,1,NULL,NULL,1,'2025-11-24 18:33:08',NULL,NULL,'Activa'),(36,2,NULL,27,'2025-11-24',NULL,'CREDITO','pruebaaas_6',1,1,NULL,NULL,1,'2025-11-24 18:39:05',NULL,NULL,'Activa'),(37,2,NULL,30,'2025-11-24',NULL,'CONTADO','N/A',1,1,NULL,NULL,1,'2025-11-24 18:44:55',NULL,NULL,'Activa'),(38,2,NULL,31,'2025-11-24',NULL,'CONTADO','yesyes',1,1,NULL,NULL,1,'2025-11-24 19:37:32',NULL,NULL,'Activa'),(39,2,NULL,32,'2025-11-24',NULL,'CREDITO','primera pueba',1,1,NULL,NULL,1,'2025-11-24 21:42:41',NULL,NULL,'Activa'),(40,2,NULL,33,'2025-11-24',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-11-24 23:02:09',NULL,NULL,'Activa'),(41,2,NULL,35,'2025-11-24',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-11-24 23:44:02',NULL,NULL,'Activa'),(42,2,NULL,36,'2025-11-24',NULL,'CONTADO','prueba de factura',1,1,NULL,NULL,1,'2025-11-24 23:56:37',NULL,NULL,'Activa'),(43,2,NULL,40,'2025-11-25',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,1,'2025-11-25 00:04:33',NULL,NULL,'Activa'),(44,2,NULL,44,'2025-11-25',NULL,'CONTADO','xxcvcxv',1,1,NULL,NULL,1,'2025-11-25 00:08:00',NULL,NULL,'Activa'),(45,1,'sd',NULL,'2025-11-25',1,'CONTADO','sdfsdfsdf',1,1,NULL,NULL,1,'2025-11-25 09:08:31',NULL,1,'Activa'),(46,2,NULL,46,'2025-11-25',NULL,'CONTADO','asdasdfasdf',1,1,NULL,NULL,1,'2025-11-25 09:25:57',NULL,NULL,'Activa'),(47,2,NULL,47,'2025-11-25',NULL,'CONTADO','kjjbliblk',1,1,NULL,NULL,1,'2025-11-25 09:30:28',NULL,NULL,'Activa'),(48,2,NULL,48,'2025-11-25',NULL,'CONTADO','JAJAJA',1,1,NULL,NULL,1,'2025-11-25 10:09:17',NULL,NULL,'Activa'),(49,1,'sd',NULL,'2025-11-25',2,'CONTADO','',1,2,NULL,NULL,1,'2025-11-25 10:18:55',NULL,1,'Activa'),(50,2,NULL,50,'2025-11-25',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-11-25 10:26:43',NULL,NULL,'Activa'),(51,2,NULL,51,'2025-11-25',NULL,'CONTADO','prubea_uno_reemplazando bodega',1,1,NULL,NULL,1,'2025-11-25 12:01:44',NULL,NULL,'Activa'),(52,2,NULL,52,'2025-11-25',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,1,'2025-11-25 12:04:30',NULL,NULL,'Activa'),(53,2,NULL,53,'2025-11-25',NULL,'CREDITO','prueba desde mobile',1,1,NULL,NULL,1,'2025-11-25 12:11:08',NULL,NULL,'Activa'),(54,2,NULL,54,'2025-11-25',NULL,'CREDITO','segunda prueba',1,1,NULL,NULL,1,'2025-11-25 12:26:03',NULL,NULL,'Activa'),(55,2,NULL,55,'2025-11-25',NULL,'CONTADO','sdfg',1,1,NULL,NULL,1,'2025-11-25 12:51:42',NULL,NULL,'Activa'),(56,2,NULL,56,'2025-11-25',NULL,'CREDITO','hjhjklñlkjhgfdssdfghjklñ',1,1,NULL,NULL,1,'2025-11-25 12:56:47',NULL,NULL,'Activa'),(57,2,NULL,57,'2025-11-25',NULL,'CREDITO','prueba',1,1,NULL,NULL,1,'2025-11-25 15:15:47',NULL,NULL,'Activa'),(58,2,NULL,58,'2025-11-25',NULL,'CONTADO','zazxczxczxc',1,1,NULL,NULL,1,'2025-11-25 15:18:54',NULL,NULL,'Activa'),(59,2,NULL,59,'2025-11-25',NULL,'CREDITO','Prueba dos con fecha correcta de factura',1,1,NULL,NULL,1,'2025-11-25 15:20:21',NULL,NULL,'Activa'),(60,2,NULL,60,'2025-11-25',NULL,'CONTADO','dfasdasdfasdfasdfasdf',1,1,NULL,NULL,1,'2025-11-25 15:22:12',NULL,NULL,'Activa'),(61,2,NULL,61,'2025-12-03',NULL,'CREDITO','Ninguno',1,1,NULL,NULL,1,'2025-12-03 15:45:48',NULL,NULL,'Activa'),(62,1,'sd',NULL,'2025-12-04',2,'CONTADO','',1,1,NULL,NULL,1,'2025-12-04 01:07:27',NULL,1,'Activa'),(63,2,NULL,62,'2025-12-08',NULL,'CONTADO','Ninguno',1,1,NULL,NULL,1,'2025-12-08 15:38:25',NULL,NULL,'Activa'),(64,2,NULL,63,'2025-12-08',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-08 15:55:31',NULL,NULL,'Activa'),(65,2,NULL,64,'2025-12-08',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-08 22:04:43',NULL,NULL,'Activa'),(66,2,NULL,65,'2025-12-09',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-09 17:22:18',NULL,NULL,'Activa'),(67,1,'',NULL,'2025-12-10',1,'CONTADO','',1,1,NULL,NULL,1,'2025-12-09 18:19:46','2025-12-09 20:34:37',1,'Activa'),(68,2,NULL,66,'2025-12-10',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,1,'2025-12-10 17:09:47',NULL,NULL,'Activa'),(69,2,NULL,67,'2025-12-10',NULL,'CREDITO','sdfdf',1,1,NULL,NULL,1,'2025-12-10 17:27:15',NULL,NULL,'Activa'),(70,2,NULL,68,'2025-12-10',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-10 17:41:51',NULL,NULL,'Activa'),(71,2,NULL,69,'2025-12-10',NULL,'CONTADO','Venta realizada | ANULADO: asdasdasdasda',1,1,NULL,NULL,1,'2025-12-10 17:42:05','2025-12-24 15:13:18',1,'Anulada'),(72,2,NULL,70,'2025-12-10',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-10 17:53:06',NULL,NULL,'Activa'),(73,2,NULL,71,'2025-12-10',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-10 18:24:46',NULL,NULL,'Activa'),(74,1,'sd',NULL,'2025-12-11',2,'CONTADO','',1,1,NULL,NULL,1,'2025-12-10 20:29:14',NULL,1,'Activa'),(75,1,'sd',NULL,'2025-12-11',2,'CONTADO',NULL,1,1,NULL,NULL,1,'2025-12-11 18:48:55',NULL,NULL,'Activa'),(76,1,'',NULL,'2025-12-12',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-12-11 18:52:01',NULL,1,'Activa'),(77,4,NULL,NULL,'2025-12-12',NULL,NULL,NULL,1,1,NULL,NULL,1,'2025-12-12 09:23:27',NULL,NULL,'Activa'),(78,1,'sd',NULL,'2025-12-13',1,'CONTADO','pruebas malisiosas',1,1,NULL,NULL,4,'2025-12-12 22:26:13',NULL,4,'Activa'),(79,2,NULL,72,'2025-12-12',NULL,'CREDITO','pruebas',1,1,NULL,NULL,4,'2025-12-12 22:26:56',NULL,NULL,'Activa'),(80,5,NULL,NULL,'2025-12-16',NULL,NULL,'Se realiza el ajuste de salida por que falto cierto producto',1,1,NULL,NULL,4,'2025-12-16 09:30:21',NULL,NULL,'Activa'),(81,7,NULL,NULL,'2025-12-16',NULL,NULL,'los ratones jugaron la comida',1,1,NULL,NULL,4,'2025-12-16 09:56:26',NULL,NULL,'Activa'),(82,2,NULL,73,'2025-12-16',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,4,'2025-12-16 10:50:33',NULL,NULL,'Activa'),(83,8,NULL,NULL,'2025-12-16',NULL,NULL,NULL,1,1,NULL,NULL,4,'2025-12-16 11:04:37',NULL,NULL,'Activa'),(84,1,'sd',NULL,'2025-12-16',1,'CONTADO','',1,1,NULL,NULL,4,'2025-12-16 11:32:08',NULL,4,'Activa'),(85,1,'',NULL,'2025-12-17',3,'CONTADO','',1,1,NULL,NULL,1,'2025-12-17 10:38:57',NULL,1,'Activa'),(86,1,'',NULL,'2025-12-17',NULL,'CONTADO','',1,1,NULL,NULL,1,'2025-12-17 13:28:42',NULL,1,'Activa'),(87,1,'',NULL,'2025-12-17',1,'CONTADO','\n[ANULADO] 2025-12-17 14:17:33 por usuario 1. Motivo: producto en mal estado',1,1,NULL,NULL,1,'2025-12-17 13:45:43','2025-12-17 14:17:33',1,'Anulada'),(88,2,'ANUL-87',NULL,'2025-12-17',1,'CONTADO','Anulación de compra #87 - producto en mal estado',1,1,NULL,NULL,1,'2025-12-17 14:17:33',NULL,NULL,'Activa'),(89,1,'prueba_56',NULL,'2025-12-17',1,'CONTADO','\n[ANULADO] 2025-12-17 14:24:35 por usuario 1. Motivo: equivocacion de huevos',1,1,NULL,NULL,1,'2025-12-17 14:21:07','2025-12-17 14:24:35',1,'Anulada'),(90,2,'ANUL-prueba_56',NULL,'2025-12-17',1,'CONTADO','Anulación de compra #89 - equivocacion de huevos',1,1,NULL,NULL,1,'2025-12-17 14:24:35',NULL,NULL,'Activa'),(91,1,'',NULL,'2025-12-17',1,'CONTADO','',1,1,NULL,NULL,1,'2025-12-17 15:05:31',NULL,1,'Activa'),(92,1,'prueba_58',NULL,'2025-12-17',1,'CONTADO','listo',1,1,NULL,NULL,1,'2025-12-17 15:09:24',NULL,1,'Activa'),(93,1,'prueba_63',NULL,'2025-12-17',1,'CONTADO','\n[ANULADA] 2025-12-17 15:26:49 por usuario 1. Motivo: porque simona la mona',1,1,NULL,NULL,1,'2025-12-17 15:26:35','2025-12-17 15:26:49',1,'Anulada'),(94,2,'ANUL-COMPRA-prueba_63',NULL,'2025-12-17',1,'CONTADO','Contramovimiento por anulación de compra #93 - porque simona la mona',1,1,NULL,NULL,1,'2025-12-17 15:26:49',NULL,NULL,'Activa'),(95,1,'',NULL,'2025-12-17',1,'CONTADO','\n[ANULADA] 2025-12-17 15:34:30 por usuario 1. Motivo: gfdfsdfgsdfgsdfg',1,1,NULL,NULL,1,'2025-12-17 15:33:10','2025-12-17 15:34:30',1,'Anulada'),(96,2,'ANUL-COMPRA-95',NULL,'2025-12-17',1,'CONTADO','Contramovimiento por anulación de compra #95 - gfdfsdfgsdfgsdfg',1,1,NULL,NULL,1,'2025-12-17 15:34:29',NULL,NULL,'Activa'),(97,1,'',NULL,'2025-12-17',1,'CONTADO','',1,1,NULL,NULL,1,'2025-12-17 15:47:01',NULL,1,'Activa'),(98,1,'222',NULL,'2025-12-20',1,'CONTADO','\n[ANULADA] 2025-12-20 08:22:04 por usuario 4. Motivo: un mal registro de mercaddo en la bodega',1,1,NULL,NULL,4,'2025-12-20 08:21:36','2025-12-20 08:22:04',4,'Anulada'),(99,9,'ANUL-COMPRA-222',NULL,'2025-12-20',1,'CONTADO','Contramovimiento por anulación de compra #98 - un mal registro de mercaddo en la bodega',1,1,NULL,NULL,4,'2025-12-20 08:22:04',NULL,NULL,'Activa'),(100,1,'',NULL,'2025-12-20',1,'CREDITO','\n[ANULADA] 2025-12-20 10:38:19 por usuario 4. Motivo: asdfasdfasdfasdfasdf',1,1,NULL,NULL,4,'2025-12-20 09:13:37','2025-12-20 10:38:19',4,'Anulada'),(101,9,'ANUL-COMPRA-100',NULL,'2025-12-20',1,'CONTADO','Contramovimiento por anulación de compra #100 - asdfasdfasdfasdfasdf',1,1,NULL,NULL,4,'2025-12-20 10:38:19',NULL,NULL,'Activa'),(102,1,'',NULL,'2025-12-22',1,'CONTADO','',1,1,NULL,NULL,4,'2025-12-22 11:49:13',NULL,4,'Activa'),(103,1,'',NULL,'2025-12-22',1,'CONTADO','',1,1,NULL,NULL,4,'2025-12-22 12:20:51',NULL,4,'Activa'),(104,1,'',NULL,'2025-12-22',1,'CREDITO','',1,1,NULL,NULL,4,'2025-12-22 12:49:24',NULL,4,'Activa'),(105,1,'sdsdfsdf',NULL,'2025-12-23',1,'CONTADO','',1,1,NULL,NULL,4,'2025-12-22 18:25:14',NULL,4,'Activa'),(106,1,'Prueba_111',NULL,'2025-12-23',1,'CREDITO','\n[ANULADA] 2025-12-22 18:26:07 por usuario 4. Motivo: Motivo de informacion mal gestionada',1,1,NULL,NULL,4,'2025-12-22 18:25:43','2025-12-22 18:26:07',4,'Anulada'),(107,9,'ANUL-COMPRA-Prueba_111',NULL,'2025-12-22',1,'CONTADO','Contramovimiento por anulación de compra #106 - Motivo de informacion mal gestionada',1,1,NULL,NULL,4,'2025-12-22 18:26:07',NULL,NULL,'Activa'),(108,1,'',NULL,'2025-12-23',1,'CREDITO','\n[ANULADA] 2025-12-22 18:27:20 por usuario 4. Motivo: mal movimiento, error al momento de seleccionar huevos',1,1,NULL,NULL,4,'2025-12-22 18:26:55','2025-12-22 18:27:20',4,'Anulada'),(109,9,'ANUL-COMPRA-108',NULL,'2025-12-22',1,'CONTADO','Contramovimiento por anulación de compra #108 - mal movimiento, error al momento de seleccionar huevos',1,1,NULL,NULL,4,'2025-12-22 18:27:20',NULL,NULL,'Activa'),(110,2,NULL,74,'2025-12-23',NULL,'CREDITO','Venta realizada | ANULADO: Anulación por usuario',1,1,NULL,NULL,4,'2025-12-23 00:54:36',NULL,NULL,'Anulada'),(111,2,NULL,75,'2025-12-23',NULL,'CREDITO','Venta realizada | ANULADO: Anulación por usuario',1,1,NULL,NULL,1,'2025-12-23 14:53:57',NULL,NULL,'Anulada'),(112,2,NULL,76,'2025-12-23',NULL,'CONTADO','Venta realizada | ANULADO: Anulación por usuario',1,1,NULL,NULL,1,'2025-12-23 15:26:01',NULL,NULL,'Anulada'),(113,1,'prueba_JAJAJA',NULL,'2025-12-23',1,'CONTADO','\n[ANULADA] 2025-12-23 15:29:05 por usuario 1. Motivo: dfsfasdfasdfasdf',1,1,NULL,NULL,1,'2025-12-23 15:28:54','2025-12-23 15:29:05',1,'Anulada'),(114,9,'ANUL-COMPRA-prueba_JAJAJA',NULL,'2025-12-23',1,'CONTADO','Contramovimiento por anulación de compra #113 - dfsfasdfasdfasdf',1,1,NULL,NULL,1,'2025-12-23 15:29:05',NULL,NULL,'Activa'),(115,2,NULL,77,'2025-12-24',NULL,'CONTADO','Venta realizada | ANULADO: wdsfsfds',1,1,NULL,NULL,1,'2025-12-24 09:58:57','2025-12-24 10:19:16',1,'Anulada'),(116,10,NULL,77,'2025-12-24',NULL,'CONTADO','Anulación venta #77 - Cliente: Jonathan - Motivo: wdsfsfds',1,1,NULL,NULL,1,'2025-12-24 10:19:16',NULL,NULL,'Activa'),(117,2,NULL,78,'2025-12-24',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,1,'2025-12-24 10:20:17',NULL,NULL,'Activa'),(118,2,NULL,79,'2025-12-24',NULL,'CONTADO','Venta realizada | ANULADO: sfsadfasdfasdf',1,1,NULL,NULL,1,'2025-12-24 10:26:43','2025-12-24 11:46:33',1,'Anulada'),(119,2,NULL,80,'2025-12-24',NULL,'CONTADO','Venta realizada | ANULADO: porque simon',1,1,NULL,NULL,1,'2025-12-24 11:00:20','2025-12-24 11:26:00',1,'Anulada'),(120,10,NULL,80,'2025-12-24',NULL,'CONTADO','Anulación venta #80 - Cliente: Josue Delgado - Motivo: porque simon',1,1,NULL,NULL,1,'2025-12-24 11:26:00',NULL,NULL,'Activa'),(121,10,NULL,79,'2025-12-24',NULL,'CONTADO','Anulación venta #79 - Cliente: Josue Delgado - Motivo: sfsadfasdfasdf',1,1,NULL,NULL,1,'2025-12-24 11:46:33',NULL,NULL,'Activa'),(122,2,NULL,81,'2025-12-24',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-24 13:41:07',NULL,NULL,'Activa'),(123,10,NULL,69,'2025-12-24',NULL,'CONTADO','Anulación venta #69 - Cliente: Fared - Motivo: asdasdasdasda',1,1,NULL,NULL,1,'2025-12-24 15:13:18',NULL,NULL,'Activa'),(124,2,NULL,82,'2025-12-24',NULL,'CREDITO','Venta realizada | ANULADO: adasdasdasd',1,1,NULL,NULL,1,'2025-12-24 15:16:17','2025-12-24 15:16:52',1,'Anulada'),(125,10,NULL,82,'2025-12-24',NULL,'CONTADO','Anulación venta #82 - Cliente: Fared - Motivo: adasdasdasd',1,1,NULL,NULL,1,'2025-12-24 15:16:52',NULL,NULL,'Activa'),(126,2,NULL,83,'2025-12-24',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-24 15:17:30',NULL,NULL,'Activa'),(127,2,NULL,84,'2025-12-24',NULL,'CREDITO','Venta realizada | ANULADO: fdgsdfgsdfg',1,1,NULL,NULL,1,'2025-12-24 15:20:48','2025-12-24 15:21:37',1,'Anulada'),(128,10,NULL,84,'2025-12-24',NULL,'CONTADO','Anulación venta #84 - Cliente: Jorges - Motivo: fdgsdfgsdfg',1,1,NULL,NULL,1,'2025-12-24 15:21:37',NULL,NULL,'Activa'),(129,2,NULL,85,'2025-12-26',NULL,'CREDITO','Venta realizada | ANULADO: dfsfsdfsdfsd',1,1,NULL,NULL,1,'2025-12-26 09:20:51','2025-12-26 09:21:15',1,'Anulada'),(130,10,NULL,85,'2025-12-26',NULL,'CONTADO','Anulación venta #85 - Cliente: Jonathan - Motivo: dfsfsdfsdfsd',1,1,NULL,NULL,1,'2025-12-26 09:21:15',NULL,NULL,'Activa'),(131,2,NULL,86,'2025-12-26',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-26 12:08:51',NULL,NULL,'Activa'),(132,2,NULL,87,'2025-12-26',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-26 12:15:00',NULL,NULL,'Activa'),(133,2,NULL,88,'2025-12-27',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-27 14:26:26',NULL,NULL,'Activa'),(134,2,NULL,89,'2025-12-27',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-27 15:22:20',NULL,NULL,'Activa'),(135,1,'',NULL,'2025-12-29',2,'CONTADO','',1,1,NULL,NULL,6,'2025-12-29 14:19:38',NULL,6,'Activa'),(136,2,NULL,90,'2025-12-30',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-30 11:05:05',NULL,NULL,'Activa'),(137,2,NULL,91,'2025-12-30',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-30 11:25:23',NULL,NULL,'Activa'),(138,2,NULL,92,'2025-12-30',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-30 11:53:31',NULL,NULL,'Activa'),(139,2,NULL,93,'2025-12-30',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2025-12-30 11:54:42',NULL,NULL,'Activa'),(140,2,NULL,94,'2025-12-30',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2025-12-30 15:14:06',NULL,NULL,'Activa'),(141,2,NULL,95,'2026-01-02',NULL,'CONTADO','Venta realizada | ANULADO: sipi comprendo todo',1,1,NULL,NULL,1,'2026-01-02 18:07:09','2026-01-02 18:12:45',1,'Anulada'),(142,10,NULL,95,'2026-01-02',NULL,'CONTADO','Anulación venta #95 - Cliente: Fared - Motivo: sipi comprendo todo',1,1,NULL,NULL,1,'2026-01-02 18:12:45',NULL,NULL,'Activa'),(143,2,NULL,96,'2026-01-05',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-05 15:41:00',NULL,NULL,'Activa'),(144,2,NULL,97,'2026-01-05',NULL,'CONTADO','Venta realizada | ANULADO: Error en la venta',1,1,NULL,NULL,1,'2026-01-05 16:39:28','2026-01-05 16:39:55',1,'Anulada'),(145,10,NULL,97,'2026-01-05',NULL,'CONTADO','Anulación venta #97 - Cliente: Clientes Varios - Motivo: Error en la venta',1,1,NULL,NULL,1,'2026-01-05 16:39:55',NULL,NULL,'Activa'),(146,2,NULL,98,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 08:35:53',NULL,NULL,'Activa'),(147,2,NULL,99,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 08:37:02',NULL,NULL,'Activa'),(148,2,NULL,100,'2026-01-06',NULL,'CONTADO','Venta realizada | ANULADO: ingreso mal de datos',1,1,NULL,NULL,6,'2026-01-06 08:38:36','2026-01-06 08:39:05',6,'Anulada'),(149,10,NULL,100,'2026-01-06',NULL,'CONTADO','Anulación venta #100 - Cliente: Fared - Motivo: ingreso mal de datos',1,1,NULL,NULL,6,'2026-01-06 08:39:05',NULL,NULL,'Activa'),(150,2,NULL,101,'2026-01-06',NULL,'CONTADO','Venta realizada | ANULADO: asdasdasdas',1,1,NULL,NULL,6,'2026-01-06 08:44:04','2026-01-06 08:44:21',6,'Anulada'),(151,10,NULL,101,'2026-01-06',NULL,'CONTADO','Anulación venta #101 - Cliente: Clientes Varios - Motivo: asdasdasdas',1,1,NULL,NULL,6,'2026-01-06 08:44:21',NULL,NULL,'Activa'),(152,2,NULL,102,'2026-01-06',NULL,'CONTADO','Venta realizada | ANULADO: JAJAJAJAJA',1,1,NULL,NULL,6,'2026-01-06 08:45:38','2026-01-06 08:46:03',6,'Anulada'),(153,10,NULL,102,'2026-01-06',NULL,'CONTADO','Anulación venta #102 - Cliente: Clientes Varios - Motivo: JAJAJAJAJA',1,1,NULL,NULL,6,'2026-01-06 08:46:03',NULL,NULL,'Activa'),(154,2,NULL,103,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 08:48:43',NULL,NULL,'Activa'),(155,2,NULL,104,'2026-01-06',NULL,'CONTADO','Venta realizada | ANULADO: mal ingreso de cantidad de producto',1,1,NULL,NULL,6,'2026-01-06 09:11:31','2026-01-06 09:13:22',6,'Anulada'),(156,10,NULL,104,'2026-01-06',NULL,'CONTADO','Anulación venta #104 - Cliente: Jahir - Motivo: mal ingreso de cantidad de producto',1,1,NULL,NULL,6,'2026-01-06 09:13:22',NULL,NULL,'Activa'),(157,2,NULL,105,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 10:52:58',NULL,NULL,'Activa'),(158,2,NULL,106,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 13:42:30',NULL,NULL,'Activa'),(159,1,'',NULL,'2026-01-06',NULL,'CONTADO','',1,1,NULL,NULL,6,'2026-01-06 13:50:37',NULL,6,'Activa'),(160,2,NULL,107,'2026-01-06',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-06 14:41:34',NULL,NULL,'Activa'),(161,2,NULL,108,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-07 08:13:21',NULL,NULL,'Activa'),(162,2,NULL,109,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-07 13:39:07',NULL,NULL,'Activa'),(163,2,NULL,110,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,6,'2026-01-07 13:40:53',NULL,NULL,'Activa'),(164,2,NULL,111,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 14:03:29',NULL,NULL,'Activa'),(165,2,NULL,112,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 14:08:44',NULL,NULL,'Activa'),(166,2,NULL,113,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 14:12:27',NULL,NULL,'Activa'),(167,2,NULL,114,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 14:13:28',NULL,NULL,'Activa'),(168,2,NULL,115,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 14:21:35',NULL,NULL,'Activa'),(169,2,NULL,116,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 15:07:01',NULL,NULL,'Activa'),(170,2,NULL,117,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 15:16:57',NULL,NULL,'Activa'),(171,2,NULL,118,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 15:37:00',NULL,NULL,'Activa'),(172,2,NULL,119,'2026-01-07',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-07 15:46:12',NULL,NULL,'Activa'),(173,2,NULL,120,'2026-01-07',NULL,'CONTADO','Venta realizada | ANULADO: mal ingreso de datos',1,1,NULL,NULL,1,'2026-01-07 15:50:27','2026-01-07 15:51:16',1,'Anulada'),(174,10,NULL,120,'2026-01-07',NULL,'CONTADO','Anulación venta #120 - Cliente: Jorges - Motivo: mal ingreso de datos',1,1,NULL,NULL,1,'2026-01-07 15:51:16',NULL,NULL,'Activa'),(175,2,NULL,121,'2026-01-07',NULL,'CONTADO','Venta realizada | ANULADO: venta incorrecta',1,1,NULL,NULL,1,'2026-01-07 16:14:59','2026-01-07 16:15:30',1,'Anulada'),(176,10,NULL,121,'2026-01-07',NULL,'CONTADO','Anulación venta #121 - Cliente: Clientes Varios - Motivo: venta incorrecta',1,1,NULL,NULL,1,'2026-01-07 16:15:30',NULL,NULL,'Activa'),(177,2,NULL,122,'2026-01-08',NULL,'CONTADO','Venta realizada | ANULADO: error',1,1,NULL,NULL,1,'2026-01-08 09:04:30','2026-01-08 09:05:07',1,'Anulada'),(178,10,NULL,122,'2026-01-08',NULL,'CONTADO','Anulación venta #122 - Cliente: Clientes Varios - Motivo: error',1,1,NULL,NULL,1,'2026-01-08 09:05:07',NULL,NULL,'Activa'),(179,2,NULL,123,'2026-01-08',NULL,'CONTADO','Venta realizada | ANULADO: sdfsdfsdfsdf',1,1,NULL,NULL,1,'2026-01-08 09:19:35','2026-01-08 09:21:00',1,'Anulada'),(180,10,NULL,123,'2026-01-08',NULL,'CONTADO','Anulación venta #123 - Cliente: Clientes Varios - Motivo: sdfsdfsdfsdf',1,1,NULL,NULL,1,'2026-01-08 09:21:00',NULL,NULL,'Activa'),(181,1,'prueba_381',NULL,'2026-01-08',NULL,'CONTADO','',1,1,NULL,NULL,1,'2026-01-08 10:07:44',NULL,1,'Activa'),(182,1,'',NULL,'2026-01-09',2,'CONTADO','',1,1,NULL,NULL,1,'2026-01-09 10:07:36',NULL,1,'Activa'),(183,2,NULL,124,'2026-01-09',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-09 13:26:51',NULL,NULL,'Activa'),(184,7,NULL,NULL,'2026-01-09',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-09 14:38:25',NULL,NULL,'Activa'),(185,2,NULL,125,'2026-01-09',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-09 15:16:42',NULL,NULL,'Activa'),(186,2,NULL,126,'2026-01-09',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,1,'2026-01-09 15:24:23',NULL,NULL,'Activa'),(187,2,NULL,127,'2026-01-09',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-09 15:26:29',NULL,NULL,'Activa'),(188,1,'',NULL,'2026-01-09',4,'CONTADO','',1,1,NULL,NULL,1,'2026-01-09 15:29:25',NULL,1,'Activa'),(189,2,NULL,128,'2026-01-09',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-09 15:47:28',NULL,NULL,'Activa'),(190,1,'',NULL,'2026-01-09',4,'CONTADO','',1,1,NULL,NULL,1,'2026-01-09 16:19:13',NULL,1,'Activa'),(191,2,NULL,129,'2026-01-10',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-10 10:16:25',NULL,NULL,'Activa'),(192,2,NULL,130,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 09:51:13',NULL,NULL,'Activa'),(193,2,NULL,131,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 09:51:48',NULL,NULL,'Activa'),(194,2,NULL,132,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 11:28:28',NULL,NULL,'Activa'),(195,2,NULL,133,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 11:56:40',NULL,NULL,'Activa'),(196,2,NULL,134,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 14:36:42',NULL,NULL,'Activa'),(197,2,NULL,135,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 15:28:20',NULL,NULL,'Activa'),(198,2,NULL,136,'2026-01-13',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-13 16:04:55',NULL,NULL,'Activa'),(199,2,NULL,137,'2026-01-14',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-14 14:22:28',NULL,NULL,'Activa'),(200,3,NULL,NULL,'2026-01-14',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-14 14:41:18',NULL,NULL,'Activa'),(201,3,NULL,NULL,'2026-01-14',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-14 14:42:36',NULL,NULL,'Activa'),(202,3,NULL,NULL,'2026-01-14',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-14 14:59:35',NULL,NULL,'Activa'),(203,2,NULL,138,'2026-01-14',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-14 15:00:46',NULL,NULL,'Activa'),(204,3,NULL,NULL,'2026-01-14',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-14 15:19:30',NULL,NULL,'Activa'),(205,2,NULL,139,'2026-01-14',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-14 15:20:06',NULL,NULL,'Activa'),(206,2,NULL,142,'2026-01-16',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-16 15:17:49',NULL,NULL,'Activa'),(207,2,NULL,143,'2026-01-16',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-16 15:27:25',NULL,NULL,'Activa'),(208,2,NULL,144,'2026-01-16',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-16 15:41:10',NULL,NULL,'Activa'),(209,2,NULL,145,'2026-01-17',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-17 08:23:30',NULL,NULL,'Activa'),(210,2,NULL,146,'2026-01-17',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-17 08:40:28',NULL,NULL,'Activa'),(211,3,NULL,NULL,'2026-01-17',NULL,NULL,NULL,1,1,NULL,NULL,8,'2026-01-17 11:05:55',NULL,NULL,'Activa'),(212,3,NULL,NULL,'2026-01-17',NULL,NULL,NULL,1,1,NULL,NULL,8,'2026-01-17 11:10:43',NULL,NULL,'Activa'),(213,2,NULL,147,'2026-01-17',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,8,'2026-01-17 11:19:05',NULL,NULL,'Activa'),(214,2,NULL,148,'2026-01-17',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,8,'2026-01-17 11:23:38',NULL,NULL,'Activa'),(215,2,NULL,149,'2026-01-19',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,8,'2026-01-19 08:44:58',NULL,NULL,'Activa'),(216,2,NULL,150,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,8,'2026-01-19 09:30:58',NULL,NULL,'Activa'),(217,2,NULL,151,'2026-01-19',NULL,'CREDITO','Venta realizada',1,1,NULL,NULL,8,'2026-01-19 09:31:21',NULL,NULL,'Activa'),(218,1,'',NULL,'2026-01-19',4,'CONTADO','',1,1,NULL,NULL,1,'2026-01-19 11:07:44',NULL,1,'Activa'),(219,2,NULL,152,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 11:13:14',NULL,NULL,'Activa'),(220,2,NULL,153,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 11:14:30',NULL,NULL,'Activa'),(221,2,NULL,154,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 12:04:55',NULL,NULL,'Activa'),(222,2,NULL,155,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 15:52:45',NULL,NULL,'Activa'),(223,2,NULL,156,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 15:53:27',NULL,NULL,'Activa'),(224,2,NULL,157,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 15:54:39',NULL,NULL,'Activa'),(225,2,NULL,158,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 15:56:58',NULL,NULL,'Activa'),(226,2,NULL,159,'2026-01-19',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-19 15:58:05',NULL,NULL,'Activa'),(227,1,'',NULL,'2026-01-19',4,'CONTADO','',1,1,NULL,NULL,1,'2026-01-19 16:06:48',NULL,1,'Activa'),(228,1,NULL,NULL,'2026-01-19',4,'CONTADO',NULL,1,1,NULL,NULL,2,'2026-01-19 16:07:50',NULL,NULL,'Activa'),(229,2,NULL,160,'2026-01-20',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-20 08:21:12',NULL,NULL,'Activa'),(230,1,'prueba_1',NULL,'2026-01-20',1,'CONTADO','',1,1,NULL,NULL,1,'2026-01-20 10:53:00',NULL,1,'Activa'),(231,3,NULL,NULL,'2026-01-21',NULL,NULL,NULL,1,1,NULL,NULL,1,'2026-01-21 08:52:08',NULL,NULL,'Activa'),(232,2,NULL,161,'2026-01-21',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,2,'2026-01-21 09:01:19',NULL,NULL,'Activa'),(233,2,NULL,162,'2026-01-22',NULL,'CONTADO','Pedido #8 - Sin observación',1,1,NULL,NULL,8,'2026-01-22 16:03:12',NULL,NULL,'Activa'),(234,2,NULL,163,'2026-01-23',NULL,'CONTADO','Pedido #9 - Sin observación',1,1,NULL,NULL,8,'2026-01-23 11:02:52',NULL,NULL,'Activa'),(235,2,NULL,164,'2026-01-23',NULL,'CONTADO','Pedido #9 - Sin observación',1,1,NULL,NULL,8,'2026-01-23 11:26:21',NULL,NULL,'Activa'),(236,2,NULL,165,'2026-01-23',NULL,'CONTADO','Pedido #10 - Sin observación',1,1,NULL,NULL,2,'2026-01-23 14:25:13',NULL,NULL,'Activa'),(237,1,'prueba_inventario',NULL,'2026-01-23',1,'CONTADO',NULL,1,1,NULL,NULL,2,'2026-01-23 15:24:32',NULL,NULL,'Activa'),(238,2,NULL,166,'2026-01-24',NULL,'CONTADO','Venta realizada',1,1,NULL,NULL,1,'2026-01-24 09:27:47',NULL,NULL,'Activa');
/*!40000 ALTER TABLE `movimientos_inventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pagos_cuentascobrar`
--

DROP TABLE IF EXISTS `pagos_cuentascobrar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pagos_cuentascobrar`
--

LOCK TABLES `pagos_cuentascobrar` WRITE;
/*!40000 ALTER TABLE `pagos_cuentascobrar` DISABLE KEYS */;
INSERT INTO `pagos_cuentascobrar` VALUES (1,19,'2025-12-10 19:15:04',3200.00,1,'nada\r\n','23232',1),(2,20,'2025-12-22 23:31:35',19000.00,1,'ninguno','etc....',4),(3,1,'2025-12-26 15:41:19',800.00,1,'sfsdfsdf','primera prueba',6),(4,2,'2025-12-26 15:50:05',160.00,1,'sdfsdf','sdfsf',6),(5,4,'2025-12-26 15:56:10',900.00,1,'sdfsdfs','dfsdfsdfsdf',6),(6,23,'2025-12-27 14:36:24',1900.00,1,'N/A','Primer pago en efectivo',6),(7,13,'2025-12-27 14:49:55',11000.50,1,'N/A','primera prueba',6),(8,18,'2025-12-27 14:56:56',800.00,1,'n/a','primer pago en efectivo',6),(9,18,'2025-12-27 14:57:58',800.00,1,'N//A','Segundo pago',6),(10,3,'2025-12-27 15:19:04',140.00,1,'N/A','primer pago',6),(11,17,'2025-12-27 15:37:49',1000.00,1,'n/a','primer pago',6),(12,17,'2025-12-27 15:40:41',60.00,1,'n/a','Segundo pago',6),(13,17,'2025-12-27 15:41:33',300.00,1,'adasdasd','tercer pago',6),(14,16,'2025-12-29 13:46:59',7000.00,1,'nada','primer pago',6),(15,5,'2025-12-30 11:09:06',3240.00,1,'n/a','primera prueba',6),(16,17,'2026-01-05 15:41:42',400.00,1,'dasdasd','23232',1),(17,5,'2026-01-06 08:52:52',3000.00,1,'N/A','Segundo pago',6),(18,6,'2026-01-06 08:54:36',300.00,1,'N/A','primer pago',6),(19,6,'2026-01-06 08:56:12',340.00,1,'','',6),(20,7,'2026-01-07 08:18:08',810.00,1,'N/A','primer pago',6);
/*!40000 ALTER TABLE `pagos_cuentascobrar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pagos_cuentaspagar`
--

DROP TABLE IF EXISTS `pagos_cuentaspagar`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pagos_cuentaspagar`
--

LOCK TABLES `pagos_cuentaspagar` WRITE;
/*!40000 ALTER TABLE `pagos_cuentaspagar` DISABLE KEYS */;
INSERT INTO `pagos_cuentaspagar` VALUES (1,1,'2025-11-16 00:00:00',10500.00,4,'dd','ddd',1),(2,1,'2025-12-20 00:00:00',10500.00,2,'23232','asdfghjkiuytre',1),(3,2,'2025-12-20 00:00:00',18000.00,1,'23232','',1),(4,3,'2025-12-22 00:00:00',12000.00,3,'1223562252','',1),(5,3,'2025-12-22 00:00:00',12000.00,1,'gvjhgvhgjh','',1),(6,4,'2025-12-23 00:00:00',7000.00,1,'ajsdasdasda','AAAAAAAA',1);
/*!40000 ALTER TABLE `pagos_cuentaspagar` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `pedidos`
--

DROP TABLE IF EXISTS `pedidos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `pedidos`
--

LOCK TABLES `pedidos` WRITE;
/*!40000 ALTER TABLE `pedidos` DISABLE KEYS */;
INSERT INTO `pedidos` VALUES (1,'2026-01-21',11,1,NULL,'Pendiente','','Retiro en local','2026-01-21 09:20:39','Normal'),(2,'2026-01-21',11,1,NULL,'Pendiente','','Retiro en local','2026-01-21 09:20:42','Normal'),(3,'2026-01-21',2,1,NULL,'Pendiente','','Retiro en local','2026-01-21 09:43:48','Normal'),(4,'2026-01-21',3,1,1,'Aprobado','','Entrega a domicilio','2026-01-21 10:58:01','Normal'),(5,'2026-01-21',11,1,1,'Pendiente','','Retiro en local','2026-01-21 14:23:12','Normal'),(6,'2026-01-21',2,1,1,'Pendiente','','Retiro en local','2026-01-21 15:27:22','Bajo'),(7,'2026-01-21',4,1,1,'Pendiente','','Entrega a domicilio','2026-01-21 15:28:34','Bajo'),(8,'2026-01-22',5,1,1,'Aprobado','','Retiro en local','2026-01-22 08:28:57','Bajo'),(9,'2026-01-23',8,1,1,'Entregado','','Entrega a domicilio','2026-01-23 11:01:55','Urgente'),(10,'2026-01-23',9,1,1,'Entregado','','Entrega a domicilio','2026-01-23 13:45:40','Normal'),(11,'2026-01-23',10,1,1,'Pendiente','','Entrega a domicilio','2026-01-23 14:39:51','Bajo');
/*!40000 ALTER TABLE `pedidos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `productos`
--

DROP TABLE IF EXISTS `productos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `productos`
--

LOCK TABLES `productos` WRITE;
/*!40000 ALTER TABLE `productos` DISABLE KEYS */;
INSERT INTO `productos` VALUES (1,'HV-0001','Extra Grande Rojo',7,'',1,180.00,1,'2025-11-12 11:46:48',1,150.00),(2,'HV-0002','Grande Rojo',7,'activo',1,190.00,1,'2025-11-13 09:44:50',1,150.00),(3,'HV-0003','Mediano Rojo',7,'activo',1,160.00,1,'2025-11-13 22:33:45',1,100.00),(4,'HV-0004','Pequeño Rojo',7,'',1,140.00,1,'2025-11-13 23:08:12',1,150.00),(5,'HV-0005','Extra Grande Blanco',7,'activo',1,200.00,1,'2025-11-15 11:35:51',1,100.00),(6,'ALM-0008','Postura Max',2,'',4,1200.00,1,'2025-11-24 18:06:45',1,10.00),(7,'HV-0010','Extra Grande Rojo',7,'activo',1,200.00,1,'2025-11-25 11:31:07',1,20.00),(8,'HV-009','Pequeño quebrado',7,'activo',1,130.00,1,'2025-12-03 16:07:08',1,100.00),(9,'ALM-0011','Postura Max',2,'inactivo',4,1500.00,1,'2025-12-03 23:46:50',1,200.00),(10,'HV-0011','Grande Blanco',7,'activo',1,190.00,1,'2026-01-06 13:49:10',1,100.00),(11,'ME-0001','Separadores',1,'activo',7,3.50,1,'2026-01-07 09:28:44',1,2500.00),(12,'ALIM-001','Jaula pro',11,'activo',4,1250.00,1,'2026-01-07 14:19:43',1,10.00),(13,'SCO-0001','Granza',10,'activo',11,70.00,1,'2026-01-14 14:40:44',1,50.00),(14,'ALIM-0002','Iniciados Brouler',11,'activo',4,1070.00,1,'2026-01-16 14:53:14',1,10.00),(15,'GAZ-0001','Gallinaza',10,'activo',12,60.00,1,'2026-01-21 08:48:44',1,10.00),(16,'HV-0012','Mediano Blanco',7,'activo',1,185.00,1,'2026-01-23 13:50:43',1,100.00);
/*!40000 ALTER TABLE `productos` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `proveedores`
--

DROP TABLE IF EXISTS `proveedores`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `proveedores`
--

LOCK TABLES `proveedores` WRITE;
/*!40000 ALTER TABLE `proveedores` DISABLE KEYS */;
INSERT INTO `proveedores` VALUES (1,'Huevos Barrancas','89562374','Nindiri, Masaya','E78522CS5544',1,'ACTIVO','2025-10-31 15:39:27',1),(2,'Granjero','89563214','nindire','',1,'ACTIVO','2025-11-23 20:07:05',1),(3,'Yema de Oro','85236974','sdfdfs','E78LK2635',1,'ACTIVO','2025-11-24 18:03:43',1),(4,'Cargill','12365478','Carretera Masaya Managua, los tanques','123654789A',1,'ACTIVO','2026-01-09 15:28:39',1);
/*!40000 ALTER TABLE `proveedores` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `roles`
--

DROP TABLE IF EXISTS `roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `roles` (
  `ID_Rol` int NOT NULL AUTO_INCREMENT,
  `Nombre_Rol` varchar(255) NOT NULL,
  `Estado` enum('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
  PRIMARY KEY (`ID_Rol`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `roles`
--

LOCK TABLES `roles` WRITE;
/*!40000 ALTER TABLE `roles` DISABLE KEYS */;
INSERT INTO `roles` VALUES (1,'Administrador','Activo'),(2,'Jefe Galera','Activo'),(3,'Bodega','Activo'),(4,'Vendedor','Activo');
/*!40000 ALTER TABLE `roles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `unidades_medida`
--

DROP TABLE IF EXISTS `unidades_medida`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `unidades_medida` (
  `ID_Unidad` int NOT NULL AUTO_INCREMENT,
  `Descripcion` varchar(255) NOT NULL,
  `Abreviatura` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`ID_Unidad`),
  UNIQUE KEY `uc_descripcion` (`Descripcion`),
  UNIQUE KEY `uc_abreviatura` (`Abreviatura`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `unidades_medida`
--

LOCK TABLES `unidades_medida` WRITE;
/*!40000 ALTER TABLE `unidades_medida` DISABLE KEYS */;
INSERT INTO `unidades_medida` VALUES (1,'Unidad','UND'),(2,'Kilogramo','KG'),(3,'Gramo','GR'),(4,'Litro','LT'),(5,'Metro','MT'),(6,'Caja','CJA'),(7,'Cajilla','CJI'),(8,'Paquete','PAQ'),(9,'Docena','DOC'),(10,'Saco','SAC'),(11,'Quintal','QQ');
/*!40000 ALTER TABLE `unidades_medida` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `usuarios`
--

DROP TABLE IF EXISTS `usuarios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
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
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `usuarios`
--

LOCK TABLES `usuarios` WRITE;
/*!40000 ALTER TABLE `usuarios` DISABLE KEYS */;
INSERT INTO `usuarios` VALUES (1,'Admin','scrypt:32768:8:1$YE2ZlcfqKZeVGLJd$ad87b14a145187f6aefa8e9e4c74e89108c49bb66e1bcf9c8417d8b8e9b32abf45424f7a51aaac88d9b843c5974de619de21ed6ea54a1d02c01e0728209bb3b0',1,'ACTIVO','2025-08-16',1),(2,'Fared','scrypt:32768:8:1$bEVWhTz12tUj9W8e$0c0fd6c352ffe83db07c4782caf668e500cae7047e483e2e10d8aa6a8a8dde9cbd7ed4cafbea19fa1b9337b4bf6f7dca93c912f6f8f3debddc163595ec4b2c48',3,'ACTIVO','2025-10-27',1),(3,'Fared@Avicola.com','scrypt:32768:8:1$o1tSL5Ky4vnr2Yx5$460a64da290850a0f915b55cb58587f4a251d46d3be44d2c12e0a7eded968ebd0bbe440512c263b60317fab5206d885d6e63f11556c802bd4d162101a9312926',1,'BLOQUEADO','2025-12-10',1),(4,'Fared_Delgado','scrypt:32768:8:1$MxpprIGUgAzVvSj2$6ace7059c74f5c485bc7a9cf36693b182101bde13bedd7650b4a7bfd40227c9b1fc1a092db306108a9f4c8da776d6a9446f8299db397b1c0b6cf4097867abf72',1,'BLOQUEADO','2025-12-12',1),(6,'Jahir','scrypt:32768:8:1$FM2o3tzX9gx7KjmO$cc7f420334144b7a063b1581c3a15507d33c93b5ff81d4467430e5b29b83c7abd2cd0704206d805ef106a7c1432ffca9ee1eef345277b391f4beab88331845d3',1,'ACTIVO','2025-12-26',1),(7,'Juan','scrypt:32768:8:1$ELYi3utnMJteQqy2$7b222de6c3a82086c04cf5a93188dc63904a0bd5e0e715f7c8fd67fda671d3d16805d39f471aeaf6c8b8dd0981e8ede5b977ea41dd3c7523b6b95dacfb99fc20',1,'ACTIVO','2025-12-30',1),(8,'Jenny','scrypt:32768:8:1$wGCym2oJcDOpF5Ga$cb13756e0510613caef6652c3af2aab53b1df44892c18fceebdebec5aeca8468db640f034990eb6cfef43ad4d228f7d769a4749b039ac85df1f79e21c7908cd8',3,'ACTIVO','2026-01-17',1),(9,'Yeri','scrypt:32768:8:1$3TzeVLNY0hqhAeiY$d17c5c730cd94cb380dd3cbceda948cd4c44fd9a671a151f73fa09b34c5b1e8a25d84a3bee0c3928eac56c17256a6ab840cf819f27196bccc06eb88964efa668',4,'ACTIVO','2026-01-24',1);
/*!40000 ALTER TABLE `usuarios` ENABLE KEYS */;
UNLOCK TABLES;

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
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-26 11:24:21
