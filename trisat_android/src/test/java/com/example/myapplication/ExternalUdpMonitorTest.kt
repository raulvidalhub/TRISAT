package com.example.myapplication

import com.example.myapplication.data.gnss.udp.ExternalUdpMonitor
import com.example.myapplication.data.gnss.udp.ExternalUdpStage
import com.example.myapplication.data.gnss.udp.checkedNmeaType
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.produceIn
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.atomic.AtomicLong

class ExternalUdpMonitorTest {
    @Test
    fun acceptsRecognizedNmeaWithValidChecksumOnly() {
        assertEquals("GGA", checkedNmeaType("$gga\r\n"))
        assertEquals("RMC", checkedNmeaType(rmc))
        assertNull(checkedNmeaType(gga.replace("*47", "*00")))
        assertNull(checkedNmeaType(gga.substringBefore('*')))
        assertNull(checkedNmeaType("$gga\n$rmc"))
        assertNull(checkedNmeaType("RAW:UBX"))
    }

    @Test
    fun distinguishesListeningUnsupportedDataAcceptedDataAndStaleData() = runBlocking {
        val clock = AtomicLong(1_000L)
        val monitor = ExternalUdpMonitor(port = 0, elapsedMillis = clock::get)
        val states = monitor.observe().produceIn(this)
        try {
            withTimeout(5_000L) {
                val listening = states.receive()
                assertEquals(ExternalUdpStage.LISTENING, listening.stage)
                assertEquals(0L, listening.datagramsReceived)
                DatagramSocket().use { sender ->
                    sender.sendTo(listening.port, """{"type":"location","source":"simulated"}""")
                    val unsupported = states.receive()
                    assertEquals(ExternalUdpStage.LISTENING, unsupported.stage)
                    assertEquals(1L, unsupported.datagramsReceived)
                    assertEquals(0L, unsupported.nmeaReceived)

                    sender.sendTo(listening.port, "$gga\r\n")
                    val receiving = states.receive()
                    assertEquals(ExternalUdpStage.RECEIVING, receiving.stage)
                    assertEquals(2L, receiving.datagramsReceived)
                    assertEquals(1L, receiving.nmeaReceived)
                    assertEquals("GGA", receiving.lastSentenceType)

                    clock.set(6_000L)
                    val stale = states.receive()
                    assertEquals(ExternalUdpStage.STALE, stale.stage)
                    assertEquals(1L, stale.nmeaReceived)

                    sender.sendTo(listening.port, rmc)
                    val recovered = states.receive()
                    assertEquals(ExternalUdpStage.RECEIVING, recovered.stage)
                    assertEquals(2L, recovered.nmeaReceived)
                    assertEquals("RMC", recovered.lastSentenceType)
                }
            }
        } finally {
            states.cancel()
        }
    }

    @Test
    fun reportsPortInUseAndCanRetryAfterItIsReleased() = runBlocking {
        DatagramSocket(0).use { occupied ->
            val port = occupied.localPort
            val monitor = ExternalUdpMonitor(port = port, elapsedMillis = { 0L })
            val status = withTimeout(5_000L) { monitor.observe().first() }
            assertEquals(ExternalUdpStage.UNAVAILABLE, status.stage)

            occupied.close()
            repeat(2) {
                val listening = withTimeout(5_000L) { monitor.observe().first() }
                assertEquals(ExternalUdpStage.LISTENING, listening.stage)
                assertEquals(port, listening.port)
            }
        }
    }

    private fun DatagramSocket.sendTo(port: Int, text: String) {
        val bytes = text.toByteArray(Charsets.US_ASCII)
        send(DatagramPacket(bytes, bytes.size, InetAddress.getByName("127.0.0.1"), port))
    }

    private companion object {
        const val gga = "\$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        const val rmc = "\$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    }
}
